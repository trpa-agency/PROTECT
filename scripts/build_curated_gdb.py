"""Build the curated PROTECT geodatabase: only the hazard and asset layers that the vulnerability
assessment and the web pages use, with only the fields they use, plus a field-level data
dictionary (table DataDictionary) and a dataset catalog (table DatasetCatalog).

    python scripts/build_curated_gdb.py                    # fails if the geodatabase exists
    python scripts/build_curated_gdb.py --overwrite        # rebuild from scratch
    python scripts/build_curated_gdb.py --resume           # finish an interrupted run, keeping what it wrote;
                                                           # also refreshes aliases, metadata, and the two tables
    python scripts/build_curated_gdb.py --include-restricted --overwrite   # NDOT rows too, F: only

A field is kept when (1) a page reads it (popup, renderer, filter, table, chart, KPI), (2) a later
pipeline step reads it back from the layer (culvert_profile.py, score_exposure.py,
score_vulnerability.py, make_pro_maps.py), (3) it is a score or a term of a score's formula (E_,
S_, V_ per pair with their indicator terms, the across-pair fields, the criticality score and its
sub-indices), or (4) it is a key or link. Delivery bookkeeping, NBI items no step reads, QA and
diagnostic fields, and intermediate hydrology stay in the analysis geodatabases.

Rows: the scored culverts and every street link, bridge, path, and transit hub that carries
scores; the classed hazard surfaces as the scoring samples them; the mapped zones and observed
records the scoring or the pages read. Sources are the ones the scoring read: the analysis and
hazards geodatabases and the services in config.yaml. Writes curated.gdb, with the two tables
also exported as CSV beside it. Run in ArcGIS Pro's Python with geopandas and pyogrio
(arcgispro-py3-plotly).

Restricted data: the NDOT rows (culverts, their inspections, and the crossings and drainage areas
they define) are left out at the row level, as publish_results.py does, so this geodatabase can be
shared. --include-restricted keeps them, writes curated.restricted_gdb instead, and refuses any
path under the repo.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from va_common import (REPO, clean, fetch_basin, get_logger, load_cfg, restricted_crossings, target_crs, to_dt,
                       withhold_pooled)

SQM_PER_ACRE = 4046.8564
SQM_PER_KM2 = 1e6


@dataclass
class Fld:
    name: str
    ftype: str            # TEXT, SHORT, LONG, DOUBLE, DATE
    alias: str
    desc: str
    units: str = ""
    values: str = ""
    used: str = ""
    src: str = ""          # <dataset>.<field>; blank = the dataset's source layer, same field name
    how: str = ""          # blank = copied as stored
    length: int | None = None


@dataclass
class Dataset:
    name: str
    group: str             # feature dataset, or "" for a table at the root
    geom: str              # POINT, POLYLINE, POLYGON, or "" for a table
    title: str
    desc: str
    source: str
    src_layer: str         # default lineage for fields without their own src
    rows: str
    key: str
    relates: str
    used: str
    fields: list


@dataclass
class Copy:
    """A straight copy of a feature class with a field subset (arcpy ExportFeatures), with the label field
    rewritten by hz_class when `labels` is given."""
    src: str
    labels: dict | None = None


# ----------------------------------------------------------------------------------------
# shared wording

V_BREAKS = "Low under 1, Medium 1 to under 2, and High 2 or more"
WF_BREAKS = "Low under 2, Medium 2 to 2.5, and High over 2.5 (decision 26)"
DF_LEFT_OUT = ("Not counted in V_max or V_class. With fire severity standing in for soil burn severity, and nearly every "
               "asset scoring 3 on drainage size, debris flow would otherwise set V_max for most assets.")
OD_ROUTE = ("Averaged over 100 stochastic assignment runs on travel time by road class "
            "(scripts/ra2ce_v2/od_stochastic_assignment.ipynb).")
PAGES_ROADS = "results.html (road layer and table on every tab)"


def road_v(e: str) -> str:
    return f"Equal to {e}, because roads have no sensitivity score (decision 25)."


def pair_words(codes: str) -> str:
    """'FLC, LSC, WFR' -> 'FL-C, LS-C, and WF-R'."""
    names = [f"{c[:2]}-{c[2:]}" for c in codes.split(", ")]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + ("," if len(names) > 2 else "") + " and " + names[-1]


def across_pairs(pairs: str, all_pairs: str, used_class: str, used_max: str, table: str = "", key: str = "") -> list:
    """V_class, V_max, V_max_pair and their all-pairs versions for one asset type. `table` is the score table they are
    joined from on `key`, blank when they sit on the asset layer itself."""
    src = (lambda n: f"{table}.{n}") if table else (lambda n: "")
    how = f"joined on {key}" if table else ""
    df = all_pairs != pairs
    classes = f"Each pair's score is classed {V_BREAKS}" + (f"; wildfire uses {WF_BREAKS}" if "WF" in pairs else "") + "."
    same = "because this asset type has no debris-flow pair"
    return [
        Fld("V_class", "TEXT", "Vulnerability class",
            f"Highest vulnerability class across {pair_words(pairs)}. {classes}"
            + (" Debris flow is left out; V_class_all includes it." if df else ""),
            values="Low, Medium, High", used=used_class, src=src("V_class"), how=how, length=10),
        Fld("V_max", "DOUBLE", "Highest vulnerability score",
            f"Highest vulnerability score across {pair_words(pairs)}." + (" Debris flow is left out." if df else ""),
            units="score, 0 to 3", used=used_max, src=src("V_max"), how=how),
        Fld("V_max_pair", "TEXT", "Pair with the highest score", "Pair that V_max comes from.", values=pairs,
            used=used_max, src=src("V_max_pair"), how=how, length=10),
        Fld("V_class_all", "TEXT", "Vulnerability class, all pairs",
            f"Highest vulnerability class across all pairs, debris flow included ({pair_words(all_pairs)})." if df
            else f"Same as V_class, {same}.", values="Low, Medium, High",
            used="publish_results.py (summary.json counts)", src=src("V_class_all"), how=how, length=10),
        Fld("V_max_all", "DOUBLE", "Highest vulnerability score, all pairs",
            f"Highest vulnerability score across all pairs, debris flow included ({pair_words(all_pairs)})." if df
            else f"Same as V_max, {same}.", units="score, 0 to 3",
            used="results.html (Overview popups)", src=src("V_max_all"), how=how),
        Fld("V_max_all_pair", "TEXT", "Pair with the highest score, all pairs",
            "Pair that V_max_all comes from." if df else f"Same as V_max_pair, {same}.", values=all_pairs,
            used="results.html (Overview popups)", src=src("V_max_all_pair"), how=how, length=10),
    ]


def c_class_inherited(asset: str) -> Fld:
    return Fld("C_class", "SHORT", "Criticality class (street link)",
               f"Criticality class of the {asset[:-1]}'s street link (Roads.C_class, through parent_segment_id).",
               values="0, 1, 2, 3 (3 is the top quarter)", src="Roads.C_class",
               how=f"looked up through parent_segment_id at build time; the analysis geodatabase does not store it on "
                   f"{asset}, and the Results and Scoring Rubrics pages look it up the same way",
               used="results.html (asset tables); scoring-rubrics.html (vulnerability by criticality matrix)")


# ----------------------------------------------------------------------------------------
# Roads

GRAVITY = "with trips split across all of them by a gravity model (beta 2)"
TRAFFIC_DEST = {
    "evacuation": ("basin exits", "to the nearest basin exit"),
    "law_enforcement": ("law enforcement", "to the nearest law enforcement station"),
    "medical_facilities": ("medical facilities", f"to medical facilities, {GRAVITY}"),
    "emergency_shelters": ("emergency shelters", f"to emergency shelters, {GRAVITY}"),
    "schools": ("schools", f"to schools, {GRAVITY}"),
    "fresh_food": ("fresh food", f"to fresh food locations, {GRAVITY}"),
}
OD_PAGE_DEST = ("evacuation", "law_enforcement", "medical_facilities", "emergency_shelters")
SNTC = "Streets_Network_Tahoe_Clean"


def roads_fields() -> list:
    f = [
        Fld("src_objectid", "LONG", "Segment ID",
            "Unique ID of the street link, its OBJECTID in Streets_Network_Tahoe and the PROTECT_VA hosted layer. Joins "
            "the road score tables; culverts and bridges store it as parent_segment_id.",
            values="unique", used=f"{PAGES_ROADS}; criticality-index.html (join key); scoring-rubrics.html (matrix); "
                               f"score_exposure.py, score_vulnerability.py, and publish_results.py (join key)"),
        Fld("segment_id", "TEXT", "Overture segment ID",
            "Overture Maps segment ID. Not unique, because Overture segments are split into several links at "
            "intersections.",
            used="od-services-index.html (popup, CSV export); workshop-feedback.html (asset ID on road notes); RA2CE v2 "
                 "pipeline (link ID)", length=64),
        Fld("name", "TEXT", "Street name", "Street name from Overture (primary name). Null if the street has no name.",
            used="results.html, criticality-index.html, od-services-index.html, and workshop-feedback.html (titles, "
                 "tables, search)", length=255),
        Fld("class", "TEXT", "Road class", "Overture road class.",
            values="trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, unknown",
            used="results.html (popups, tables, miles by road type); criticality-index.html; od-services-index.html; "
                 "workshop-feedback.html", length=32),
        Fld("In_Basin", "SHORT", "In basin",
            "1 if the link is inside the Lake Tahoe basin. Every link here is 1; the Workshop Feedback page filters on it.",
            values="1", used="workshop-feedback.html (layer filter, read from PROTECT_VA)"),
        Fld("seg_len_m", "DOUBLE", "Length (m)", "Link length measured from the geometry, rounded to 0.1 m.",
            units="meters", src="Vulnerability_roads.seg_len_m", how="joined on src_objectid",
            used="results.html (road miles in KPIs, charts, and tables); criticality-index.html (miles); "
                 "publish_results.py (summary)"),
        Fld("C_class", "SHORT", "Criticality class",
            "The criticality percentile cut into quarters at the 25th, 50th, and 75th percentiles.",
            values="0, 1, 2, 3 (3 is the top quarter)", src="Vulnerability_roads.C_class",
            how="joined on src_objectid",
            used="results.html (line weight on every tab, tables, Overview matrix and hotspots); scoring-rubrics.html "
                 "(matrix); publish_results.py (matrix, hotspots)"),
        Fld("criticality_pctl", "DOUBLE", "Criticality percentile", "Percentile rank of criticality_score, 0 to 100.",
            units="percentile", used="results.html (popups); criticality-index.html; score_vulnerability.py (C_class)"),
        Fld("criticality_score", "DOUBLE", "Criticality score",
            "0.3 x traffic_subindex + 0.3 x detour_subindex + 0.3 x od_subindex + 0.1 x equity_subindex, calculated in "
            "scripts/Streets_Network_Clean.ipynb. The Criticality page recalculates it from its own weight sliders.",
            units="weighted z-score", used="criticality-index.html; results.html (Overview); score_vulnerability.py"),
        Fld("traffic_subindex", "DOUBLE", "Traffic sub-index",
            "AADT_Jenks_Score as a z-score (mean 0, population standard deviation).", units="z-score",
            used="criticality_score (weight 0.3)"),
        Fld("detour_subindex", "DOUBLE", "Detour sub-index", "SLR_Diff_Length_Jenks_Score as a z-score.",
            units="z-score", used="criticality_score (weight 0.3)"),
        Fld("od_subindex", "DOUBLE", "OD traffic sub-index", "OD_Traffic_Jenks_Score as a z-score.",
            units="z-score", used="criticality_score (weight 0.3)"),
        Fld("equity_subindex", "DOUBLE", "Equity sub-index",
            "Average of the z-scores of the four block group counts: Below_Poverty_Household_max, "
            "Speak_English_Not_Well_Not_at_A_max, Vehicle_Available_0_max, and With_Disability_max.", units="z-score",
            used="criticality_score (weight 0.1)"),
        Fld("AADT_Jenks_Score", "SHORT", "Traffic score (1 to 10)",
            "Estimated_2024_AADT_Filled grouped into 10 classes by Jenks natural breaks.", values="1 to 10",
            used="criticality-index.html (traffic sub-index); traffic_subindex"),
        Fld("Estimated_2024_AADT_Filled", "LONG", "Average daily traffic (2024)",
            "Average annual daily traffic from StreetLight's 2024 estimates, matched to the link by best overlap (5 m "
            "buffer, at least half the link's length). Unmatched major roads take the highest value among the links they "
            "touch; other unmatched links are 0.",
            units="vehicles per day",
            used="workshop-feedback.html (road note subtitle, read from PROTECT_VA); AADT_Jenks_Score"),
        Fld("SLR_Diff_Length_Jenks_Score", "SHORT", "Detour score (1 to 10)",
            "slr_diff_length_max grouped into 10 Jenks classes. Links with no value score 1.", values="1 to 10",
            used="criticality-index.html (detour sub-index); detour_subindex"),
        Fld("slr_diff_length_max", "DOUBLE", "Detour length (m)",
            "Extra distance of the shortest detour if the link is closed, from RA2CE single-link redundancy on the "
            "corrected v2 network (scripts/ra2ce_v2). 0 where there is no detour, except on major roads, which take the "
            "highest value of their neighbors.", units="meters",
            used="criticality-index.html (detour view); SLR_Diff_Length_Jenks_Score"),
        Fld("OD_Traffic_Jenks_Score", "SHORT", "OD traffic score (1 to 10)",
            "OD_Traffic_Avg grouped into 10 Jenks classes.", values="1 to 10",
            used="criticality-index.html (OD sub-index); od_subindex"),
        Fld("OD_Traffic_Avg", "DOUBLE", "OD traffic, average of six", "Average of the six traffic_* fields.",
            units="persons", used="criticality-index.html; OD_Traffic_Jenks_Score"),
    ]
    for d, (label, rule) in TRAFFIC_DEST.items():
        page = ("criticality-index.html (OD sub-index, destination toggles); od-services-index.html (Traffic ranking, "
                "via roads_od.json); OD_Traffic_Avg" if d in OD_PAGE_DEST
                else "criticality-index.html (OD sub-index); OD_Traffic_Avg")
        f.append(Fld(f"traffic_{d}", "DOUBLE", f"Residents routed to {label}",
                     f"Residents routed over the link {rule}. {OD_ROUTE}", units="persons", used=page))
    for d in OD_PAGE_DEST:
        label = TRAFFIC_DEST[d][0]
        f.append(Fld(f"prioritarian_{d}", "DOUBLE", f"Equity-weighted residents routed to {label}",
                     f"Same as traffic_{d}, with each origin weighted by 1 plus its normalized poverty rate.",
                     units="weighted persons", used="od-services-index.html (Prioritarian ranking, via roads_od.json)"))
    for name, what, unit in (("Below_Poverty_Household_max", "Households below the poverty line", "households"),
                             ("Speak_English_Not_Well_Not_at_A_max", "People who speak English not well or not at all", "persons"),
                             ("Vehicle_Available_0_max", "Households with no vehicle", "households"),
                             ("With_Disability_max", "People with a disability", "persons")):
        f.append(Fld(name, "DOUBLE", what + " (block group)",
                     f"{what} in the census block group the link touches (Block_Group_Layer). A link that touches several "
                     f"block groups takes the highest value, and one that touches none takes the nearest block group's.",
                     units=unit, used="criticality-index.html (equity sub-index); equity_subindex"))
    f += across_pairs("FLR, LSR, WFR, AVR", "FLR, LSR, WFR, DFR, AVR",
                      "results.html (Overview color and Priority view, hotspots, tables); scoring-rubrics.html; "
                      "publish_results.py (summary)",
                      "results.html (Overview popups)", "Vulnerability_roads", "src_objectid")
    # flooding
    f += [
        Fld("E_FLR_hist", "DOUBLE", "Flood exposure (FL-R)",
            "Highest flood class the link touches in Hazard_Flood_Class: 3 for a FEMA 1 percent zone, 2 for the 0.2 "
            "percent zone or within 10 m of a mapped stream, and 0 for neither.", values="0, 2, 3",
            src="Exposure_flood_roads.E_FLR_hist", how="joined on src_objectid",
            used="results.html (Flooding tab color, popup, table, charts)"),
        Fld("FLR_len_pct_c2", "DOUBLE", "Percent of length in flood class 2",
            "Percent of the link's length in flood class 2.", units="percent", src="Exposure_flood_roads.len_pct_c2",
            how="joined on src_objectid; renamed from len_pct_c2", used="results.html (Flooding popup)"),
        Fld("FLR_len_pct_c3", "DOUBLE", "Percent of length in flood class 3",
            "Percent of the link's length in flood class 3 (FEMA 1 percent zone).", units="percent",
            src="Exposure_flood_roads.len_pct_c3", how="joined on src_objectid; renamed from len_pct_c3",
            used="results.html (Flooding popup)"),
        Fld("V_FLR_hist", "DOUBLE", "Flood vulnerability (FL-R)", road_v("E_FLR_hist"),
            values="0 (Low), 2 (Medium), 3 (High)", src="Vulnerability_roads.V_FLR_hist", how="joined on src_objectid",
            used="results.html (Overview Flooding view, popups); scoring-rubrics.html (matrix)"),
    ]
    # landslide
    f += [
        Fld("E_LSR_hist", "DOUBLE", "Landslide exposure (LS-R)",
            "(0.50 x E_LSR_e1 + 0.20 x E_LSR_e2) / 0.70. E_LSR_e2 is 0 at the historical horizon, so this is 0.714 x "
            "E_LSR_e1.", values="0, 0.71, 1.43, 2.14", src="Exposure_landslide_roads.E_LSR_hist",
            how="joined on src_objectid", used="results.html (Landslide tab color, popup, table, charts)"),
        Fld("E_LSR_e1", "DOUBLE", "Landslide susceptibility class (LS-R E1)",
            "Highest landslide class the link touches in Hazard_Landslide_Class.", values="0 to 3",
            src="Exposure_landslide_roads.E_LSR_e1", how="joined on src_objectid",
            used="results.html (Landslide popup, table, KPI); E_LSR_hist (weight 0.50)"),
        Fld("E_LSR_e2", "DOUBLE", "Precipitation change (LS-R E2)",
            "Cal-Adapt precipitation change. Always 0 at the historical horizon; the 2050 and 2080 columns will be added "
            "in December.", values="0", src="Exposure_landslide_roads.E_LSR_e2",
            how="joined on src_objectid", used="E_LSR_hist (weight 0.20)"),
    ]
    f += [Fld(f"LSR_len_pct_c{k}", "DOUBLE", f"Percent of length in landslide class {k}",
              f"Percent of the link's length in landslide class {k}.", units="percent",
              src=f"Exposure_landslide_roads.len_pct_c{k}", how=f"joined on src_objectid; renamed from len_pct_c{k}",
              used="results.html (Landslide popup and table)") for k in (1, 2, 3)]
    f += [Fld("V_LSR_hist", "DOUBLE", "Landslide vulnerability (LS-R)", road_v("E_LSR_hist"),
              values=V_BREAKS, src="Vulnerability_roads.V_LSR_hist", how="joined on src_objectid",
              used="results.html (Overview Landslide view, popups); scoring-rubrics.html (matrix)")]
    # wildfire
    f += [
        Fld("E_WFR_hist", "DOUBLE", "Wildfire exposure (WF-R)", "0.70 x E_WFR_e1 + 0.30 x E_WFR_e2.",
            units="score, 0 to 3", src="Exposure_wildfire_roads.E_WFR_hist", how="joined on src_objectid",
            used="results.html (Wildfire tab color, popup, table, charts, KPIs)"),
        Fld("E_WFR_e1", "DOUBLE", "Burn probability class (WF-R E1)",
            "Highest burn probability class within 300 ft of the link (Hazard_Wildfire_BurnProb).",
            values="0 to 3", src="Exposure_wildfire_roads.E_WFR_e1", how="joined on src_objectid",
            used="results.html (Wildfire popup, table); E_WFR_hist (weight 0.70)"),
        Fld("E_WFR_e2", "DOUBLE", "Fire severity class (WF-R E2)",
            "Highest fire severity class that covers at least 25 percent of the 300 ft buffer around the link "
            "(Hazard_Wildfire_Severity).", values="0 to 3", src="Exposure_wildfire_roads.E_WFR_e2",
            how="joined on src_objectid", used="results.html (Wildfire popup, table, KPI); E_WFR_hist (weight 0.30)"),
    ]
    f += [Fld(f"WFR_len_pct_c{k}", "DOUBLE", f"Percent of length in burn probability class {k}",
              f"Percent of the link's own length (not its 300 ft buffer) in burn probability class {k}.",
              units="percent", src=f"Exposure_wildfire_roads.len_pct_c{k}",
              how=f"joined on src_objectid; renamed from len_pct_c{k}",
              used="results.html (Wildfire popup and table)") for k in (1, 2, 3)]
    f += [Fld("V_WFR_hist", "DOUBLE", "Wildfire vulnerability (WF-R)", road_v("E_WFR_hist"),
              values=WF_BREAKS, src="Vulnerability_roads.V_WFR_hist", how="joined on src_objectid",
              used="results.html (Overview Wildfire view, popups); scoring-rubrics.html (matrix)")]
    # debris flow
    f += [
        Fld("E_DFR_hist", "DOUBLE", "Debris-flow exposure (DF-R)",
            f"(0.20 x E_DFR_e1 + 0.20 x E_DFR_e2 + 0.30 x E_DFR_e3) / 0.70 (rubric 4.2, option 1). {DF_LEFT_OUT}",
            units="score, 0 to 3", src="Exposure_debris_flow_roads.E_DFR_hist", how="joined on src_objectid",
            used="results.html (Debris flow tab color, popup, table, chart)"),
        Fld("E_DFR_e1", "DOUBLE", "Upslope steepness score (DF-R E1)",
            "Highest upslope steepness score the link touches in Hazard_DebrisFlow_Slope.",
            values="0 to 3 in half points", src="Exposure_debris_flow_roads.E_DFR_e1", how="joined on src_objectid",
            used="results.html (Debris flow popup, table); E_DFR_hist (weight 0.20)"),
        Fld("E_DFR_e2", "DOUBLE", "Drainage size score (DF-R E2)",
            "Score of the largest drainage area the link touches in Hazard_DebrisFlow_Area. Smaller drainages score "
            "higher.", values="0 to 3 in half points", src="Exposure_debris_flow_roads.E_DFR_e2",
            how="joined on src_objectid", used="results.html (Debris flow popup, table); E_DFR_hist (weight 0.20)"),
        Fld("E_DFR_e3", "DOUBLE", "Fire severity class (DF-R E3)",
            "Highest fire severity class the link touches in Hazard_Wildfire_Severity. It stands in for predicted soil "
            "burn severity, which is under contract.", values="0 to 3", src="Exposure_debris_flow_roads.E_DFR_e3",
            how="joined on src_objectid; renamed from E_e3 where the score table still uses the old name",
            used="results.html (Debris flow popup and table); E_DFR_hist (weight 0.30)"),
        Fld("V_DFR_hist", "DOUBLE", "Debris-flow vulnerability (DF-R)", road_v("E_DFR_hist"),
            values=V_BREAKS, src="Vulnerability_roads.V_DFR_hist", how="joined on src_objectid",
            used="results.html (Overview Debris flow view, popups); scoring-rubrics.html (matrix)"),
    ]
    # avalanche
    f += [
        Fld("E_AVR_hist", "DOUBLE", "Avalanche exposure (AV-R)",
            "Scored from av_tier and av_record. With no avalanche zone within 1,000 ft, tiers 0 to 3 score 0, 1, 1.5, "
            "and 2; with a zone, they score 1, 2, 2.5, and 3.", values="0, 1, 1.5, 2, 2.5, 3",
            src="Exposure_avalanche_roads.E_AVR_hist", how="joined on src_objectid",
            used="results.html (Avalanche tab color, popup, table, charts)"),
        Fld("av_tier", "SHORT", "Uphill slope tier",
            "Slope tier covering the most uphill ground within 1,000 ft of the link (ties go to the higher tier). Uphill "
            "means 10 m cells at least one 20 m elevation band above the link's midpoint. Tier 0 is under 25 degrees; 1 "
            "is 25 to under 30 or over 50; 2 is 30 to under 35 or over 45 to 50; 3 is 35 to 45. Null where no ground is "
            "uphill, which scores as tier 0.", values="0, 1, 2, 3",
            src="Exposure_avalanche_roads.av_tier", how="joined on src_objectid",
            used="results.html (Avalanche tier view, popup, table, chart)"),
        Fld("av_record", "SHORT", "Avalanche zone within 1,000 ft",
            "1 if a TRPA avalanche zone (Avalanche_Zones) is within 1,000 ft of the link.", values="0, 1",
            src="Exposure_avalanche_roads.av_record", how="joined on src_objectid",
            used="results.html (Avalanche popup, table, chart, KPI)"),
        Fld("uphill_ha", "DOUBLE", "Uphill ground within 1,000 ft (ha)",
            "Area of the uphill ground that av_tier is taken from.", units="hectares",
            src="Exposure_avalanche_roads.uphill_ha", how="joined on src_objectid",
            used="results.html (Avalanche popup, table)"),
        Fld("V_AVR_hist", "DOUBLE", "Avalanche vulnerability (AV-R)", road_v("E_AVR_hist"),
            values=V_BREAKS, src="Vulnerability_roads.V_AVR_hist", how="joined on src_objectid",
            used="results.html (Overview Avalanche view, popups); scoring-rubrics.html (matrix)"),
    ]
    # screening flags the criticality and OD pages filter on
    f += [
        Fld("in_flood_zone", "SHORT", "In a FEMA flood zone (screening)",
            "1 if the link touches any FEMA flood zone, 100- or 500-year, including the lake's stillwater zone. Used as "
            "a page filter; the assessment's flood score is E_FLR_hist.", values="0, 1",
            used="criticality-index.html (hazard filter); od-services-index.html (hazard filter, via roads_od.json)"),
        Fld("in_flood_zone_100", "SHORT", "In a FEMA 100-year zone (screening)",
            "1 if the link touches a FEMA 100-year flood zone (FLOOD_YEAR '100-year flood').", values="0, 1",
            used="criticality-index.html (hazard filter)"),
        Fld("high_sev_fire", "SHORT", "In probable high-severity fire area (screening)",
            "1 if the link touches the probable high-severity fire area "
            "(ForestManagementZone_Identity_HighSeverityProbability, gridcode 1). Used as a page filter; the "
            "assessment's wildfire score is E_WFR_hist.", values="0, 1",
            used="criticality-index.html (hazard filter); od-services-index.html (hazard filter)"),
        Fld("landslide_mean", "DOUBLE", "Landslide susceptibility, average (screening)",
            "Average USGS 2024 landslide susceptibility over the 90 m cells the link crosses. Each cell holds the count "
            "of landslide-prone 10 m cells inside it, 0 to 81.", units="10 m cells per 90 m cell",
            used="criticality-index.html (hazard filter); od-services-index.html (hazard filter at 22 or more, via "
                 "roads_od.json)"),
    ]
    return f


# ----------------------------------------------------------------------------------------
# Culverts and their tables

def culverts_fields() -> list:
    f = [
        Fld("culvert_id", "TEXT", "Culvert ID",
            "The jurisdiction and the agency's own asset ID, joined by a vertical bar.",
            values="<jurisdiction>|<agency ID>, unique",
            used="results.html (popup titles, culvert table); workshop-feedback.html (asset ID); "
                 "tahoe-precip-events.html; the scoring scripts (join key)", length=160),
        Fld("jurisdiction", "TEXT", "Jurisdiction", "Agency that provided the record.",
            values="Caltrans, City of South Lake Tahoe, Douglas County, El Dorado County, Placer County, Washoe County, "
                   "TRPA Legacy (provisional)",
            used="results.html (popups, table, charts by jurisdiction); workshop-feedback.html; "
                 "tahoe-precip-events.html; culvert_profile.py (condition rating scheme)", length=60),
        Fld("road_name", "TEXT", "Road", "Road over the culvert, as the agency recorded it. Null if not given.",
            used="results.html (popups, table); workshop-feedback.html; tahoe-precip-events.html", length=254),
        Fld("parent_segment_id", "LONG", "Parent street link",
            "src_objectid of the nearest street link within 50 m (Roads). The culvert's criticality comes from this "
            "link.",
            how="stored as text in the analysis geodatabase; converted to an integer to match Roads.src_objectid",
            used="results.html (criticality in the culvert table); scoring-rubrics.html (matrix); culvert_profile.py "
                 "(breach lines, delineation set)"),
        Fld("crossing_id", "TEXT", "Crossing",
            "Crossing the culvert belongs to. Culverts within 10 m of each other on the same link form one crossing, "
            "whose drainage area is in CulvertWatersheds. A few crossings have no polygon there: those whose pour point "
            "was not found (scored on 25 m around the culvert instead), and those shared with a restricted-jurisdiction "
            "culvert, whose drainage area is withheld.", values="X plus five digits",
            used="results.html (popup, table, drainage area on click); score_exposure.py (watershed sampling)",
            length=12),
        Fld("barrels", "SHORT", "Barrels", "Number of culverts in the crossing. Null where the crossing includes a "
            "restricted-jurisdiction culvert, as are q_cap_crossing_cfs, the loading ratios, and ratio_review.",
            values="1 or more",
            used="results.html (popup); culvert_profile.py (crossing capacity)"),
        Fld("material", "TEXT", "Material (as recorded)",
            "Pipe material as the agency recorded it, in words or as a code.",
            used="tahoe-precip-events.html (popup); culvert_profile.py (material_class)", length=60),
        Fld("material_class", "TEXT", "Material class", "Pipe material grouped into the same classes for every agency.",
            values="corrodible_metal, plastic, concrete, unknown",
            used="results.html (popup); culvert_profile.py (inlet-control coefficients)", length=20),
        Fld("xsection_shape", "TEXT", "Cross-section shape (as recorded)",
            "Cross-section shape as the agency recorded it, in words or as a code.",
            used="culvert_profile.py (round versus box or arch, for d_eq_in and capacity)", length=80),
        Fld("span_in", "DOUBLE", "Span (in)", "Opening width (the diameter for round pipes).", units="inches",
            how="set to null if 0 or less (including -9999), over 576 in., or a round span over 144 in. "
                "(culvert_profile.clean_span_rise, the same rule as the profile and the published files); the analysis "
                "geodatabase keeps the original value",
            used="tahoe-precip-events.html (popup); scoring-rubrics.html (calculator); culvert_profile.py (d_eq_in, "
                 "capacity)"),
        Fld("rise_in", "DOUBLE", "Rise (in)", "Opening height for boxes, arches, and ellipses.", units="inches",
            how="set to null if 0 or less (culvert_profile.clean_span_rise)",
            used="culvert_profile.py (d_eq_in, capacity)"),
        Fld("d_eq_in", "DOUBLE", "Equivalent diameter (in)",
            "span_in for round pipes. For other shapes, the diameter of a circle with area span x rise, which is the "
            "square root of (4 x span x rise / pi). Null where size is missing.", units="inches",
            used="results.html (popup, table); workshop-feedback.html; scoring-rubrics.html; score_vulnerability.py "
                 "(LS-C and DF-C S1)"),
        Fld("size_class", "TEXT", "Size class",
            "d_eq_in in four bands: small is 18 in. or less, medium over 18 to 36, large over 36 to 72, and major over "
            "72.", values="small, medium, large, major", used="results.html (loading ratio chart by size)", length=10),
        Fld("length_ft", "DOUBLE", "Length (ft)",
            "Pipe length as the agency recorded it. Not checked; a few very short or very long values are probably entry "
            "errors or whole pipe runs.", units="feet", how="set to null if 0 or less",
            used="tahoe-precip-events.html (popup)"),
        Fld("inlet_type", "TEXT", "Inlet type (as recorded)",
            "Inlet end treatment as the agency recorded it, in words or as a code.",
            used="culvert_profile.py (inlet-control coefficients)", length=60),
        Fld("install_year", "SHORT", "Year installed",
            "Year installed. Only El Dorado County and the City of South Lake Tahoe provide it. Crossings built in 2011 "
            "or later are newer than the 2010 lidar the drainage areas are based on.", units="year",
            how="set to null if before 1900 (0, the two-digit entries 50 and 89, and El Dorado County's 1801 "
                "placeholder); the analysis geodatabase keeps the original value",
            used="culvert_profile.py (check against the lidar date)"),
        Fld("data_source", "TEXT", "Source file", "File or service the record came from.",
            used="tahoe-precip-events.html (popup)", length=160),
        Fld("contrib_area_ac", "DOUBLE", "Drainage area (ac)",
            "Area of the full watershed draining to the crossing, including ground that drains through other crossings "
            "upstream.", units="acres",
            used="results.html (popup, table); scoring-rubrics.html; score_exposure.py (DF-C E2)"),
        Fld("basin_slope_pct", "DOUBLE", "Basin slope (percent)", "Area-weighted average slope of the full watershed.",
            units="percent", used="scoring-rubrics.html; score_exposure.py (DF-C E1); score_vulnerability.py (FL-C S1)"),
        Fld("basin_landcover", "TEXT", "Main land cover", "Most common NLCD 2021 land cover group in the watershed.",
            values="forest, shrub, grass, developed, barren, water, wetland",
            used="results.html (popup); score_vulnerability.py (FL-C S1)", length=20),
        Fld("q_method", "TEXT", "Flow method", "Method used to estimate the 100-year flow.",
            values="rational (under 1 sq mi), regression_CA (Gotvald 2012, Lahontan region), regression_NV (Thomas 1997, "
                   "region 1), regression_needed, none (no watershed)", used="results.html (popup, table)", length=20),
        Fld("q_event_100_cfs", "DOUBLE", "100-year flow (cfs)",
            "100-year peak flow at the crossing. Basins under 1 sq mi use the rational method with NOAA Atlas 14 "
            "rainfall intensity at the Kirpich time of concentration; larger basins use the USGS regional regression.",
            units="cubic feet per second", used="results.html (popup, table)"),
        Fld("q_cap_crossing_cfs", "DOUBLE", "Crossing capacity (cfs)",
            "Flow the crossing can pass with water at the top of the opening (FHWA HDS-5 inlet control, 2 percent slope "
            "assumed), summed over all barrels. Null where a barrel is restricted-jurisdiction.",
            units="cubic feet per second", used="results.html (popup, table)"),
        Fld("load_ratio_100", "DOUBLE", "Loading ratio, 100-year",
            "q_event_100_cfs divided by q_cap_crossing_cfs. Above 1, the 100-year flow is more than the crossing can "
            "pass. Null where size, watershed, or flow is missing, where size_suspect is 1, or where a barrel in the "
            "crossing is restricted-jurisdiction.", units="ratio",
            used="results.html (popup, table, chart, KPIs); workshop-feedback.html; make_pro_maps.py; "
                 "score_vulnerability.py (FL-C S2)"),
        Fld("cond_class", "SHORT", "Condition class",
            "Condition from the latest inspection, on one scale for every agency from 0 (good) to 3 (poor). It is the "
            "higher of the condition rating and the blockage class, or 1 where there is no rating.",
            values="0, 1, 2, 3",
            used="results.html (popup, table); workshop-feedback.html; scoring-rubrics.html; score_vulnerability.py "
                 "(condition indicators)"),
        Fld("cond_source", "TEXT", "Condition source",
            "Whether cond_class comes from a condition rating, from blockage alone, or is the default.",
            values="rated, blockage_only, default",
            used="results.html (popup); workshop-feedback.html; score_vulnerability.py (default handling)", length=20),
        Fld("blockage_pct", "DOUBLE", "Blockage (percent)", "Percent of the opening blocked at the latest inspection.",
            units="percent", used="tahoe-precip-events.html; score_vulnerability.py (FL-C S3, DF-C S2)"),
        Fld("tailwater_flag", "SHORT", "Tailwater flag",
            "1 if the pour point is below 6,230 ft, just above the lake's legal maximum of 6,229.1 ft, so a high lake "
            "can back water into the outlet. Adds 1 to E_FLC_hist, up to 3.", values="0, 1",
            used="results.html (popup, flags); score_exposure.py (FL-C adjustment)"),
        Fld("on_stream", "SHORT", "On a mapped stream",
            "1 if the culvert is within 10 m of a stream or lake in the lidar-derived streams layer.", values="0, 1",
            used="results.html (table flags)"),
        Fld("size_suspect", "SHORT", "Size suspect",
            "1 if the recorded size is too small to be plausible for the drainage area: 24 in. or less on a mapped "
            "stream draining 100 acres or more, 24 in. or less draining 500 acres or more anywhere, or any size under 8 "
            "in. The loading ratio is left null and the record goes to the owner to confirm.", values="0, 1",
            used="results.html (popup, owner-review filter, KPI)"),
        Fld("ratio_review", "SHORT", "Ratio review",
            "1 if load_ratio_100 is over 20. The culvert is still scored and is listed for the owner to confirm. "
            "Null where the loading ratio is withheld for a restricted-jurisdiction barrel.",
            values="0, 1", used="results.html (popup, owner-review filter)"),
        Fld("profile_completeness", "TEXT", "Profile completeness",
            "Whether size, drainage area, and condition are all known (full), some are (partial), or none are "
            "(default).", values="full, partial, default",
            used="results.html (KPI for culverts with size, drainage, and condition all known)", length=10),
        c_class_inherited("culverts"),
    ]
    f += across_pairs("FLC, LSC", "FLC, LSC, DFC",
                      "results.html (Overview color, popups); scoring-rubrics.html; publish_results.py (summary)",
                      "results.html (Overview and Flooding popups)")
    f += [
        Fld("S_source", "TEXT", "Sensitivity data",
            "Whether the sensitivity indicators used recorded data (full), only defaults (default), or a mix (partial).",
            values="full, partial, default", used="results.html (popups, culvert table)", length=10),
        # flooding
        Fld("E_FLC_hist", "DOUBLE", "Flood exposure (FL-C)",
            "Highest flood class anywhere in the culvert's full watershed, or within 25 m of the culvert where no "
            "watershed was delineated. Raised by 1, up to 3, where tailwater_flag is 1.", values="0, 1, 2, 3",
            used="results.html (popup, table, chart)"),
        Fld("E_FLC_pt", "DOUBLE", "Flood exposure at the culvert",
            "Highest flood class within 25 m of the culvert, without the tailwater adjustment. For comparison with "
            "E_FLC_hist.", values="0, 2, 3", used="results.html (Flooding popup)"),
        Fld("S_FLC_s1", "DOUBLE", "Debris potential (FL-C S1)",
            "Debris potential from the draft methodology's matrix of basin slope (8 percent or less, over 8 to 16, over "
            "16) and land cover (water and snow, urban, shrubs, trees). 1 where slope or land cover is missing.",
            values="0 to 3 in half points", used="S_FLC (weight 0.25)"),
        Fld("S_FLC_s2", "DOUBLE", "Loading ratio score (FL-C S2)",
            "Score for load_ratio_100: 3 for a ratio of 4 or more, 2.5 for 3 to under 4, 2 for 2.5 to under 3, 1.5 for 2 "
            "to under 2.5, 1 for 1.5 to under 2, 0.5 for 1 to under 1.5, and 0 under 1. 1 where the ratio is null.",
            values="0 to 3 in half points", used="S_FLC (weight 0.30)"),
        Fld("S_FLC_s3", "DOUBLE", "Condition and blockage score (FL-C S3)",
            "The higher of the condition score (1 good to 3 poor) and the blockage score (1 under 25 percent, 2 for 25 "
            "to under 50, 3 for 50 or more). 2 where no inspection gives a rating or blockage. Added by TRPA; the draft "
            "methodology has only S1 and S2.",
            values="1, 2, 3", used="S_FLC (weight 0.15)"),
        Fld("S_FLC", "DOUBLE", "Flood sensitivity (FL-C)",
            "(0.25 x S_FLC_s1 + 0.30 x S_FLC_s2 + 0.15 x S_FLC_s3) / 0.70.", units="score, 0 to 3",
            used="results.html (Flooding popup); V_FLC_hist (weight 0.70)"),
        Fld("V_FLC_hist", "DOUBLE", "Flood vulnerability (FL-C)", "0.30 x E_FLC_hist + 0.70 x S_FLC.",
            values=V_BREAKS, used="results.html (popups, table, KPI); scoring-rubrics.html (matrix)"),
        # landslide
        Fld("E_LSC_hist", "DOUBLE", "Landslide exposure (LS-C)",
            "(0.50 x E_LSC_e1 + 0.20 x E_LSC_e2) / 0.70. E_LSC_e2 is 0 at the historical horizon.",
            values="0, 0.71, 1.43, 2.14", used="results.html (Landslide color, popup)"),
        Fld("E_LSC_e1", "DOUBLE", "Landslide susceptibility class (LS-C E1)",
            "Highest landslide class anywhere in the culvert's watershed, or within 25 m of the culvert where there is "
            "no watershed.", values="0 to 3",
            used="results.html (Landslide popup, KPI); E_LSC_hist (weight 0.50)"),
        Fld("E_LSC_e2", "DOUBLE", "Precipitation change (LS-C E2)",
            "Cal-Adapt precipitation change. Always 0 at the historical horizon.", values="0",
            used="E_LSC_hist (weight 0.20)"),
        Fld("E_LSC_pt", "DOUBLE", "Landslide exposure at the culvert",
            "E_LSC_hist with E1 taken within 25 m of the culvert instead of over the watershed.",
            values="0, 0.71, 1.43, 2.14", used="results.html (Landslide popup)"),
        Fld("S_LSC_s1", "DOUBLE", "Opening size score (LS-C S1)",
            "Score for d_eq_in: 3 under 24 in., 2.5 for 24 to under 36, 2 for 36 to under 60, 1.5 for 60 to under 84, "
            "and 1 for 84 or more. 2 where size is missing.", values="1 to 3 in half points",
            used="S_LSC (weight 0.15)"),
        Fld("S_LSC_s2", "DOUBLE", "Condition score (LS-C S2)",
            "Condition score from cond_class, 1 (good) to 3 (poor). 2 where there is no rating.", values="1, 2, 3",
            used="S_LSC (weight 0.15)"),
        Fld("S_LSC", "DOUBLE", "Landslide sensitivity (LS-C)", "(0.15 x S_LSC_s1 + 0.15 x S_LSC_s2) / 0.30.",
            units="score, 0 to 3", used="V_LSC_hist (weight 0.30)"),
        Fld("V_LSC_hist", "DOUBLE", "Landslide vulnerability (LS-C)", "0.70 x E_LSC_hist + 0.30 x S_LSC.",
            values=V_BREAKS, used="results.html (Overview and Landslide popups); scoring-rubrics.html (matrix)"),
        # debris flow
        Fld("E_DFC_hist", "DOUBLE", "Debris-flow exposure (DF-C)",
            f"(0.20 x E_DFC_e1 + 0.20 x E_DFC_e2 + 0.30 x E_DFC_e3) / 0.70 (rubric 4.2, option 1). {DF_LEFT_OUT}",
            units="score, 0 to 3", used="results.html (Debris flow color, popup, chart)"),
        Fld("E_DFC_e1", "DOUBLE", "Basin slope score (DF-C E1)",
            "Score for basin_slope_pct: 3 over 30 percent, 2.5 over 25, 2 over 20, 1.5 over 15, 1 over 10, 0.5 over 5, "
            "and 0 otherwise.", values="0 to 3 in half points",
            used="results.html (Debris flow popup); E_DFC_hist (weight 0.20)"),
        Fld("E_DFC_e2", "DOUBLE", "Basin size score (DF-C E2)",
            "Score for contrib_area_ac in square miles: 3 under 0.25, 2.5 up to 0.5, 2 up to 1, 1.5 up to 2, 1 up to 3, "
            "0.5 up to 5, and 0 over 5.", values="0 to 3 in half points",
            used="results.html (Debris flow popup); E_DFC_hist (weight 0.20)"),
        Fld("E_DFC_e3", "DOUBLE", "Fire severity class (DF-C E3)",
            "Highest fire severity class in the watershed (Hazard_Wildfire_Severity). It stands in for predicted soil "
            "burn severity, which is under contract.", values="1, 2, 3",
            used="results.html (Debris flow popup); E_DFC_hist (weight 0.30)"),
        Fld("DF_option", "TEXT", "Debris-flow method", "Debris-flow scoring option used (rubric 4.2).",
            values="1 (fire severity stand-in)", used="results.html (Debris flow popup); scoring-rubrics.html",
            length=24),
        Fld("S_DFC_s1", "DOUBLE", "Opening size score (DF-C S1)", "Same scale as S_LSC_s1 (decision 7).",
            values="1 to 3 in half points", used="S_DFC (weight 0.15)"),
        Fld("S_DFC_s2", "DOUBLE", "Condition and blockage score (DF-C S2)", "Same scale as S_FLC_s3.",
            values="1, 2, 3", used="S_DFC (weight 0.15)"),
        Fld("S_DFC", "DOUBLE", "Debris-flow sensitivity (DF-C)", "(0.15 x S_DFC_s1 + 0.15 x S_DFC_s2) / 0.30.",
            units="score, 0 to 3", used="V_DFC_hist (weight 0.30)"),
        Fld("V_DFC_hist", "DOUBLE", "Debris-flow vulnerability (DF-C)",
            "0.70 x E_DFC_hist + 0.30 x S_DFC. Not counted in V_max or V_class.", values=V_BREAKS,
            used="results.html (Overview and Debris flow popups); scoring-rubrics.html (matrix)"),
    ]
    return f


CONDITION_FIELDS = [
    Fld("culvert_id", "TEXT", "Culvert ID", "Culvert the inspection belongs to (Culverts.culvert_id).",
        used="tahoe-precip-events.html; culvert_profile.py (latest inspection per culvert)", length=160),
    Fld("jurisdiction", "TEXT", "Jurisdiction",
        "Agency that reported the inspection. It sets how condition_rating is read.",
        used="culvert_profile.py (rating scheme by agency)", length=60),
    Fld("inspection_date", "DATE", "Inspection date", "Date of the inspection. Null if the agency did not give one.",
        used="tahoe-precip-events.html (popup); culvert_profile.py (latest inspection)"),
    Fld("condition_rating", "TEXT", "Condition rating (as recorded)",
        "Condition rating as the agency recorded it. Its meaning depends on condition_scheme.",
        used="tahoe-precip-events.html (popup); culvert_profile.py (cond_class)", length=30),
    Fld("condition_scheme", "TEXT", "Rating scheme",
        "Rating scheme the agency uses: Placer 1 to 5, Douglas maintenance score, TRPA legacy text, Washoe structural "
        "code, or Caltrans date only.", used="tahoe-precip-events.html (popup)", length=120),
    Fld("blockage_pct", "DOUBLE", "Blockage (percent)", "Percent of the opening blocked at the inspection.",
        units="percent", used="tahoe-precip-events.html (popup); culvert_profile.py (cond_class, blockage)"),
]

WATERSHED_FIELDS = [
    Fld("crossing_id", "TEXT", "Crossing", "Crossing this drainage area belongs to (Culverts.crossing_id).",
        values="X plus five digits, unique",
        used="results.html (drainage area on click); score_exposure.py (watershed sampling)", length=12),
    Fld("downstream_crossing_id", "TEXT", "Next crossing downstream",
        "Next crossing downstream. Null at an outlet, where the link to the next crossing was cut, or where the next "
        "crossing is withheld (restricted jurisdiction).",
        how="set to null where the next crossing is not in this layer",
        used="score_exposure.py (upstream maximum over the drainage tree); publish_results.py (upstream drainage files)",
        length=12),
    Fld("area_ac", "DOUBLE", "Direct drainage area (ac)",
        "Area of this polygon, which covers the ground that drains to the crossing without passing through another "
        "crossing first.", units="acres", how="calculated from the geometry at build time",
        used="results.html (drainage area popup, as the direct area)"),
    Fld("contrib_area_ac", "DOUBLE", "Full drainage area (ac)",
        "Area of this polygon plus every polygon upstream of it, which is the whole watershed at the crossing. Includes "
        "ground that drains through a withheld crossing.", units="acres", src="CulvertCrossings.contrib_area_ac",
        how="joined on crossing_id", used="results.html (popup); score_exposure.py (DF-C E2, through Culverts)"),
]


# ----------------------------------------------------------------------------------------
# Bridges, paths, hubs

def bridges_fields() -> list:
    f = [
        Fld("bridge_id", "TEXT", "NBI structure number", "NBI structure number (item 8), unique within the state.",
            used="results.html (popups); workshop-feedback.html (asset ID); the scoring scripts (join key)", length=20),
        Fld("state", "TEXT", "State", "State (NBI item 1).", values="CA, NV", used="results.html (table)", length=2),
        Fld("owner", "TEXT", "Owner", "Owner, decoded from NBI item 22.",
            used="results.html (popups); workshop-feedback.html", length=60),
        Fld("facility_carried", "TEXT", "Facility carried",
            "Road or facility on the bridge (NBI item 7). NBI's 'NO DATA ENTERED' placeholder is left as is.",
            used="results.html (popup titles); workshop-feedback.html", length=40),
        Fld("feature_crossed", "TEXT", "Feature crossed",
            "Feature under the bridge (NBI item 6A). NBI's 'NO DATA ENTERED' placeholder is left as is.",
            used="results.html (popup titles); workshop-feedback.html", length=40),
        Fld("year_built", "SHORT", "Year built", "Year built (NBI item 27).", units="year",
            used="results.html (Flooding popup); workshop-feedback.html"),
        Fld("parent_segment_id", "LONG", "Parent street link",
            "src_objectid of the nearest street link within 50 m (Roads).",
            how="stored as text in the analysis geodatabase; converted to an integer to match Roads.src_objectid",
            used="results.html (criticality); scoring-rubrics.html (matrix)"),
        Fld("is_culvert_type", "SHORT", "NBI culvert type",
            "1 if NBI item 43B is 19, a culvert over 20 ft. These large culverts are scored as bridges.", values="0, 1",
            used="culvert_profile.py (inventory culverts within 25 m of one are not scored as culverts)"),
        Fld("main_spans", "SHORT", "Spans in the main unit", "Number of spans in the main unit (NBI item 45).",
            used="score_vulnerability.py (span type: FL-B S3, LS-B S1, DF-B S1)"),
        Fld("max_span_m", "DOUBLE", "Longest span (m)", "Length of the longest span (NBI item 48).", units="meters",
            used="scoring-rubrics.html; score_vulnerability.py (span length: LS-B S3, DF-B S3)"),
        Fld("waterway_eval", "TEXT", "Waterway adequacy (NBI 71)", "Waterway adequacy appraisal (NBI item 71).",
            values="0 to 9, N (not over a waterway)",
            used="results.html (Flooding popup); scoring-rubrics.html; score_exposure.py (FL-B E1)", length=1),
        Fld("channel_cond", "TEXT", "Channel condition (NBI 61)",
            "Channel and channel protection condition (NBI item 61).",
            values="0 to 9, N", used="scoring-rubrics.html; score_vulnerability.py (FL-B S1)", length=1),
        Fld("scour_code", "TEXT", "Scour critical (NBI 113)", "Scour-critical code (NBI item 113).",
            values="0 to 9, N, U, T", used="scoring-rubrics.html; score_vulnerability.py (FL-B S2)", length=1),
        Fld("scour_label", "TEXT", "Scour", "scour_code in words.", used="results.html (Flooding popup)", length=50),
        Fld("lowest_rating", "SHORT", "Lowest condition rating",
            "Lowest of the deck, superstructure, and substructure ratings (NBI items 58 to 60), or the culvert rating "
            "(item 62) for culverts.", values="0 to 9",
            used="scoring-rubrics.html; make_pro_maps.py; score_vulnerability.py (FL-B S4, LS-B S2, DF-B S2)"),
        Fld("bridge_condition_label", "TEXT", "Condition", "NBI overall bridge condition.",
            values="Good, Fair, Poor", used="results.html (Flooding popup); workshop-feedback.html", length=10),
        c_class_inherited("bridges"),
    ]
    f += across_pairs("FLB, LSB", "FLB, LSB, DFB",
                      "results.html (Overview color, popups); scoring-rubrics.html; publish_results.py",
                      "results.html (Overview popups)")
    f += [
        Fld("S_source", "TEXT", "Sensitivity data",
            "Whether the sensitivity indicators used recorded data (full), only defaults (default), or a mix (partial), "
            "taking the least complete pair. A blank NBI item counts as a default.",
            values="full, partial, default", used="results.html (popups)", length=10),
        Fld("E_FLB_hist", "DOUBLE", "Flood exposure (FL-B)", "(0.20 x E_FLB_e1 + 0.10 x E_FLB_e2) / 0.30.",
            units="score, 0 to 3", used="results.html (Flooding color, popup)"),
        Fld("E_FLB_e1", "DOUBLE", "Waterway adequacy score (FL-B E1)",
            "Score for waterway_eval (NBI item 71): 3 for codes 0 or 1, 2.5 for 2 or 3, 2 for 4 or 5, 1.5 for 6, 1 for 7 "
            "or 8, 0.5 for 9, 0 for N, and 1 if blank.", values="0 to 3 in half points",
            used="E_FLB_hist (weight 0.20)"),
        Fld("E_FLB_e2", "DOUBLE", "Flood class within 25 m (FL-B E2)",
            "Highest flood class within 25 m of the bridge (Hazard_Flood_Class).", values="0, 2, 3",
            used="E_FLB_hist (weight 0.10)"),
        Fld("S_FLB_s1", "DOUBLE", "Channel condition score (FL-B S1)",
            "Score for channel_cond (NBI item 61): 3 for codes 0 to 2, 2.5 for 3, 2 for 4, 1.5 for 5, 1 for 6 or 7, 0.5 "
            "for 8, 9, or N, and 1 if blank (TRPA default).", values="0.5 to 3", used="S_FLB (weight 0.10)"),
        Fld("S_FLB_s2", "DOUBLE", "Scour score (FL-B S2)",
            "Score for scour_code (NBI item 113): 3 for code 1, 2.5 for 2, 2 for 3, 1.5 for 4, and 1 for 5 to 9, U, N, "
            "or blank.", values="1 to 3", used="S_FLB (weight 0.40)"),
        Fld("S_FLB_s3", "DOUBLE", "Span type score (FL-B S3)",
            "Score for main_spans (NBI item 45): 3 for a single span, and 1 for more than one or blank.",
            values="1, 3", used="S_FLB (weight 0.10)"),
        Fld("S_FLB_s4", "DOUBLE", "Condition score (FL-B S4)",
            "Score for lowest_rating: 3 for 0 to 2, 2.5 for 3 or 4, 2 for 5, 1.5 for 6, and 1 for 7 to 9, N, or none.",
            values="1 to 3", used="S_FLB (weight 0.10)"),
        Fld("S_FLB", "DOUBLE", "Flood sensitivity (FL-B)",
            "(0.10 x S_FLB_s1 + 0.40 x S_FLB_s2 + 0.10 x S_FLB_s3 + 0.10 x S_FLB_s4) / 0.70.", units="score, 0 to 3",
            used="results.html (Flooding popup); V_FLB_hist (weight 0.70)"),
        Fld("V_FLB_hist", "DOUBLE", "Flood vulnerability (FL-B)", "0.30 x E_FLB_hist + 0.70 x S_FLB.",
            values=V_BREAKS, used="results.html (Overview and Flooding popups); scoring-rubrics.html (matrix)"),
        Fld("E_LSB_hist", "DOUBLE", "Landslide exposure (LS-B)",
            "(0.50 x E_LSB_e1 + 0.20 x E_LSB_e2) / 0.70. E_LSB_e2 is 0 at the historical horizon.",
            values="0, 0.71, 1.43, 2.14", used="results.html (Landslide color, popup)"),
        Fld("E_LSB_e1", "DOUBLE", "Landslide class within 25 m (LS-B E1)",
            "Highest landslide class within 25 m of the bridge (Hazard_Landslide_Class).", values="0 to 3",
            used="results.html (Landslide popup, KPI); E_LSB_hist (weight 0.50)"),
        Fld("E_LSB_e2", "DOUBLE", "Precipitation change (LS-B E2)",
            "Cal-Adapt precipitation change. Always 0 at the historical horizon.", values="0",
            used="E_LSB_hist (weight 0.20)"),
        Fld("S_LSB_s1", "DOUBLE", "Span type score (LS-B S1)", "Same scale as S_FLB_s3.", values="1, 3",
            used="S_LSB (weight 0.10)"),
        Fld("S_LSB_s2", "DOUBLE", "Condition score (LS-B S2)", "Same scale as S_FLB_s4.", values="1 to 3",
            used="S_LSB (weight 0.10)"),
        Fld("S_LSB_s3", "DOUBLE", "Span length score (LS-B S3)",
            "Score for max_span_m in feet. Longer spans score higher, as in the draft (decision 12): 3 over 500 ft, 2.5 "
            "over 350, 2 over 200, 1.5 over 100, 1 over 50, 0.5 over 20, 0 otherwise, and 1 if blank.",
            values="0 to 3 in half points", used="S_LSB (weight 0.10)"),
        Fld("S_LSB", "DOUBLE", "Landslide sensitivity (LS-B)",
            "(0.10 x S_LSB_s1 + 0.10 x S_LSB_s2 + 0.10 x S_LSB_s3) / 0.30.", units="score, 0 to 3",
            used="V_LSB_hist (weight 0.30)"),
        Fld("V_LSB_hist", "DOUBLE", "Landslide vulnerability (LS-B)", "0.70 x E_LSB_hist + 0.30 x S_LSB.",
            values=V_BREAKS, used="results.html (Overview and Landslide popups); scoring-rubrics.html (matrix)"),
        Fld("E_DFB_hist", "DOUBLE", "Debris-flow exposure (DF-B)",
            f"(0.20 x E_DFB_e1 + 0.20 x E_DFB_e2 + 0.30 x E_DFB_e3) / 0.70 (rubric 4.2, option 1). {DF_LEFT_OUT}",
            units="score, 0 to 3", used="results.html (Debris flow color, popup)"),
        Fld("E_DFB_e1", "DOUBLE", "Upslope steepness score (DF-B E1)",
            "Highest upslope steepness score within 25 m of the bridge (Hazard_DebrisFlow_Slope).",
            values="0 to 3 in half points", used="E_DFB_hist (weight 0.20)"),
        Fld("E_DFB_e2", "DOUBLE", "Drainage size score (DF-B E2)",
            "Score of the largest drainage area within 25 m of the bridge (Hazard_DebrisFlow_Area).",
            values="0 to 3 in half points", used="E_DFB_hist (weight 0.20)"),
        Fld("E_DFB_e3", "DOUBLE", "Fire severity class (DF-B E3)",
            "Highest fire severity class within 25 m of the bridge (Hazard_Wildfire_Severity). It stands in for "
            "predicted soil burn severity, which is under contract.", values="0 to 3", used="E_DFB_hist (weight 0.30)"),
        Fld("DF_option", "TEXT", "Debris-flow method", "Debris-flow scoring option used (rubric 4.2).",
            values="1 (fire severity stand-in)", used="results.html (Debris flow popup); scoring-rubrics.html",
            length=24),
        Fld("S_DFB_s1", "DOUBLE", "Span type score (DF-B S1)", "Same scale as S_FLB_s3.", values="1, 3",
            used="S_DFB (weight 0.10)"),
        Fld("S_DFB_s2", "DOUBLE", "Condition score (DF-B S2)", "Same scale as S_FLB_s4.", values="1 to 3",
            used="S_DFB (weight 0.10)"),
        Fld("S_DFB_s3", "DOUBLE", "Span length score (DF-B S3)", "Same scale as S_LSB_s3.",
            values="0 to 3 in half points", used="S_DFB (weight 0.10)"),
        Fld("S_DFB", "DOUBLE", "Debris-flow sensitivity (DF-B)",
            "(0.10 x S_DFB_s1 + 0.10 x S_DFB_s2 + 0.10 x S_DFB_s3) / 0.30.", units="score, 0 to 3",
            used="V_DFB_hist (weight 0.30)"),
        Fld("V_DFB_hist", "DOUBLE", "Debris-flow vulnerability (DF-B)",
            "0.70 x E_DFB_hist + 0.30 x S_DFB. Not counted in V_max or V_class.", values=V_BREAKS,
            used="results.html (Overview and Debris flow popups); scoring-rubrics.html (matrix)"),
    ]
    return f


def paths_fields() -> list:
    vt = "Vulnerability_active_transport"
    f = [
        Fld("at_id", "LONG", "Path ID",
            "OBJECTID of the facility in the TRPA Transportation service (layer 3). Joins the path score tables.",
            values="unique", src=f"{vt}.at_id (Transportation/MapServer/3.OBJECTID)",
            how="stored as text in the score tables; converted to an integer",
            used="results.html (Wildfire and Overview path layers); workshop-feedback.html (asset ID); the scoring "
                 "scripts (join key)"),
        Fld("name", "TEXT", "Name", "Facility name.", src="Transportation/MapServer/3.NAME", how="renamed from NAME",
            used="results.html (popups); workshop-feedback.html", length=30),
        Fld("class", "TEXT", "Facility class", "Facility class, such as Class 1 shared-use path or Class 2 bike lane.",
            src="Transportation/MapServer/3.CLASS", how="renamed from CLASS",
            used="results.html (popups); workshop-feedback.html", length=20),
        Fld("maint_jurs", "TEXT", "Maintaining jurisdiction", "Jurisdiction that maintains the facility.",
            src="Transportation/MapServer/3.MAINT_JURS", how="renamed from MAINT_JURS",
            used="workshop-feedback.html (asset card)", length=100),
        Fld("miles", "DOUBLE", "Miles (as published)", "Length as published in the service.", units="miles",
            src="Transportation/MapServer/3.MILES", how="renamed from MILES", used="workshop-feedback.html (asset card)"),
        Fld("seg_len_m", "DOUBLE", "Length (m)", "Length measured from the geometry.", units="meters",
            src=f"{vt}.seg_len_m", how="joined on at_id", used="results.html (path miles in KPIs and charts)"),
    ]
    f += across_pairs("FLAT, WFAT", "FLAT, WFAT", "results.html (Overview color, popups); publish_results.py (summary)",
                      "results.html (Overview popups)", vt, "at_id")
    f += [
        Fld("S_source", "TEXT", "Sensitivity data",
            "Always default, because the FL-AT sensitivity indicators use the draft methodology's default values.",
            values="default", src=f"{vt}.S_source", how="joined on at_id", used="publish_results.py", length=10),
        Fld("E_FLAT_hist", "DOUBLE", "Flood exposure (FL-AT)",
            "Highest flood class the path touches (Hazard_Flood_Class).", values="0, 2, 3",
            src=f"{vt}.E_FLAT_hist", how="joined on at_id", used="V_FLAT_hist (weight 0.70)"),
        Fld("S_FLAT", "DOUBLE", "Flood sensitivity (FL-AT)",
            "Fixed at 2 by the draft methodology's defaults. Surface (S1) is unknown and scored as unpaved, 3; trail "
            "slope (S2) is unknown and scored 1. With weights of 0.15 each, (0.15 x 3 + 0.15 x 1) / 0.30 = 2.",
            values="2", src=f"{vt}.S_FLAT", how="joined on at_id", used="V_FLAT_hist (weight 0.30)"),
        Fld("V_FLAT_hist", "DOUBLE", "Flood vulnerability (FL-AT)", "0.70 x E_FLAT_hist + 0.30 x S_FLAT.",
            values=V_BREAKS, src=f"{vt}.V_FLAT_hist", how="joined on at_id",
            used="results.html (Overview Flooding view)"),
        Fld("E_WFAT_hist", "DOUBLE", "Wildfire exposure (WF-AT)", "0.70 x E_WFAT_e1 + 0.30 x E_WFAT_e2.",
            units="score, 0 to 3", src=f"{vt}.E_WFAT_hist", how="joined on at_id",
            used="results.html (Wildfire color, popup, KPI)"),
        Fld("E_WFAT_e1", "DOUBLE", "Burn probability class (WF-AT E1)",
            "Highest burn probability class within 300 ft of the path (Hazard_Wildfire_BurnProb).", values="0 to 3",
            src="Exposure_wildfire_active_transport.E_WFAT_e1", how="joined on at_id",
            used="results.html (Wildfire popup); E_WFAT_hist (weight 0.70)"),
        Fld("E_WFAT_e2", "DOUBLE", "Fire severity class (WF-AT E2)",
            "Highest fire severity class that covers at least 25 percent of the 300 ft buffer around the path "
            "(Hazard_Wildfire_Severity).", values="0 to 3", src="Exposure_wildfire_active_transport.E_WFAT_e2",
            how="joined on at_id", used="results.html (Wildfire popup); E_WFAT_hist (weight 0.30)"),
        Fld("V_WFAT_hist", "DOUBLE", "Wildfire vulnerability (WF-AT)",
            "Equal to E_WFAT_hist, because wildfire on paths has no sensitivity score.",
            values=WF_BREAKS, src=f"{vt}.V_WFAT_hist", how="joined on at_id",
            used="results.html (Overview Wildfire view)"),
    ]
    return f


def hubs_fields() -> list:
    vt = "Vulnerability_transit_centers"
    f = [Fld("tc_id", "LONG", "Hub ID", "FID of the hub in the Transit_Hubs hosted layer. Joins the hub score tables.",
             values="unique", src=f"{vt}.tc_id (Transit_Hubs/FeatureServer/0.FID)",
             how="stored as text in the score tables; converted to an integer",
             used="results.html (hub popup title, 'Transit hub {tc_id}'); the scoring scripts (join key)")]
    f += across_pairs("FLTC, WFTC", "FLTC, WFTC", "results.html (Overview color, popups); publish_results.py (summary)",
                      "results.html (Overview popups)", vt, "tc_id")
    f += [
        Fld("S_source", "TEXT", "Sensitivity data",
            "Always full, because the transit hub pairs have no sensitivity indicators.", values="full",
            src=f"{vt}.S_source", how="joined on tc_id", used="publish_results.py", length=10),
        Fld("E_FLTC_hist", "DOUBLE", "Flood exposure (FL-TC)",
            "Highest flood class within 25 m of the hub (Hazard_Flood_Class).", values="0, 2, 3",
            src=f"{vt}.E_FLTC_hist", how="joined on tc_id", used="V_FLTC_hist"),
        Fld("V_FLTC_hist", "DOUBLE", "Flood vulnerability (FL-TC)",
            "Equal to E_FLTC_hist, because transit hubs have no sensitivity score.",
            values=V_BREAKS, src=f"{vt}.V_FLTC_hist", how="joined on tc_id", used="results.html (Overview)"),
        Fld("E_WFTC_hist", "DOUBLE", "Wildfire exposure (WF-TC)", "0.70 x E_WFTC_e1 + 0.30 x E_WFTC_e2.",
            units="score, 0 to 3", src=f"{vt}.E_WFTC_hist", how="joined on tc_id",
            used="results.html (Wildfire color, popup, KPI)"),
        Fld("E_WFTC_e1", "DOUBLE", "Burn probability class (WF-TC E1)",
            "Highest burn probability class within 300 ft of the hub (Hazard_Wildfire_BurnProb).", values="0 to 3",
            src="Exposure_wildfire_transit_centers.E_WFTC_e1", how="joined on tc_id",
            used="results.html (Wildfire popup); E_WFTC_hist (weight 0.70)"),
        Fld("E_WFTC_e2", "DOUBLE", "Fire severity class (WF-TC E2)",
            "Highest fire severity class that covers at least 25 percent of the 300 ft buffer around the hub "
            "(Hazard_Wildfire_Severity).", values="0 to 3", src="Exposure_wildfire_transit_centers.E_WFTC_e2",
            how="joined on tc_id", used="results.html (Wildfire popup); E_WFTC_hist (weight 0.30)"),
        Fld("V_WFTC_hist", "DOUBLE", "Wildfire vulnerability (WF-TC)",
            "Equal to E_WFTC_hist, because transit hubs have no sensitivity score.",
            values=WF_BREAKS, src=f"{vt}.V_WFTC_hist", how="joined on tc_id", used="results.html (Overview)"),
    ]
    return f


# ----------------------------------------------------------------------------------------
# hazard surfaces and sources

def surface_fields(label_text: str, values: str, used: str, half_points: bool = False, label: bool = True,
                   label_how: str = "") -> list:
    f = [Fld("hz_class", "DOUBLE" if half_points else "SHORT", "Hazard class", label_text, values=values, used=used)]
    if label:
        f.append(Fld("label", "TEXT", "Class label", "The class described in words.",
                     used="results.html (surface popups)", how=label_how, length=80))
    return f


LANDSLIDE_LABEL_HOW = ("rewritten from hz_class with score_exposure.landslide_labels; the hazards geodatabase keeps the "
                       "older 1 to 5 class wording until the surface is rebuilt")

AVALANCHE_FIELDS = [
    Fld("tier", "SHORT", "Slope tier",
        "Slope tier of the 10 m cell. Tier 0 is under 25 degrees; 1 is 25 to under 30 or over 50; 2 is 30 to under 35 "
        "or over 45 to 50; 3 is 35 to 45.", values="0, 1, 2, 3",
        used="score_exposure.py, through surfaces_dfav.py (av_tier on Roads)"),
    Fld("band_m", "DOUBLE", "Elevation band (m)",
        "Bottom of the cell's 20 m elevation band. Cells at least one band above a link's midpoint count as uphill.",
        units="meters", used="score_exposure.py, through surfaces_dfav.py (uphill test for av_tier)"),
]

RECORD_FIELDS = {
    "Avalanche_Zones": [
        Fld("Name", "TEXT", "Zone name", "Name of the avalanche zone.", used="results.html (Avalanche zone popup)",
            length=50),
        Fld("Frequency", "TEXT", "Frequency", "Avalanche frequency recorded for the zone.",
            used="results.html (Avalanche zone popup)", length=10),
    ],
    "FEMA_Flood_Zones": [
        Fld("FLOOD_ZONE", "TEXT", "FEMA zone", "FEMA flood zone designation.",
            used="score_exposure.py (flood class 3 for A, AE, AH, and AO zones; 2 for 0.2 percent zones)", length=50),
        Fld("FLOOD_YEAR", "TEXT", "Flood year", "Return period of the flood the zone represents.",
            values="100-year flood, 500-year flood",
            used="score_exposure.py (flood class); Streets_Network_Clean.ipynb (in_flood_zone_100)", length=255),
    ],
    "Landslide_Inventory_Polygons": None,   # filled below (shared with points)
    "Fire_Perimeters": [
        Fld("YEAR_", "SHORT", "Fire year", "Year of the fire.", units="year",
            used="historic-hazards.html (color ramp, year filter, table); workshop-feedback.html (context popup)"),
        Fld("FIRE_NAME", "TEXT", "Fire name", "Name of the fire.", used="historic-hazards.html (popup, table)",
            length=34),
        Fld("GIS_ACRES", "DOUBLE", "Acres", "Mapped fire area.", units="acres",
            used="historic-hazards.html (popup, table)"),
        Fld("ALARM_DATE", "DATE", "Alarm date", "Date the fire was reported.",
            used="historic-hazards.html (popup, table)"),
        Fld("CONT_DATE", "DATE", "Containment date", "Date the fire was contained.",
            used="historic-hazards.html (popup)"),
        Fld("CAUSE", "SHORT", "Cause code",
            "CAL FIRE cause code: 1 lightning, 2 equipment use, 3 smoking, 4 campfire, 5 debris, 6 railroad, 7 arson, 8 "
            "playing with fire, 9 miscellaneous, 10 vehicle, 11 electrical power, 12 firefighter training, 13 "
            "non-firefighter training, 14 unknown, 15 structure, 16 aircraft.", values="1 to 16",
            used="historic-hazards.html (popup, table, decoded)"),
        Fld("AGENCY", "TEXT", "Reporting agency code",
            "Reporting agency: CDF CAL FIRE, USF USDA Forest Service, NPS, BLM, BIA, FWS, DOD, CCO contract county, LRA "
            "local response area, PVT private, NOP no protection, OTH other.",
            used="historic-hazards.html (popup, table, decoded)", length=3),
        Fld("UNIT_ID", "TEXT", "Unit", "Reporting unit code.", used="historic-hazards.html (popup)", length=3),
    ],
    "Earthquakes": [
        Fld("event_id", "TEXT", "ComCat event ID", "USGS ComCat event ID.", src="ComCat.id", how="renamed from id",
            used="historic-hazards.html (feature identity)", length=40),
        Fld("mag", "DOUBLE", "Magnitude", "Magnitude of the earthquake.", values="2.5 or more",
            used="historic-hazards.html (symbol size, popup)"),
        Fld("place", "TEXT", "Location", "Location description from ComCat.", used="historic-hazards.html (popup)",
            length=200),
        Fld("event_time", "DATE", "Origin time (UTC)", "Origin time of the earthquake, in UTC.", src="ComCat.time",
            how="renamed from time; converted from epoch milliseconds to a date", used="historic-hazards.html (popup)"),
    ],
}
LANDSLIDE_RECORD_FIELDS = [
    Fld("USGS_ID", "TEXT", "USGS ID", "USGS inventory record ID.", used="historic-hazards.html (popup)", length=254),
    Fld("LS_Type", "TEXT", "Landslide type", "Landslide type, as compiled in the inventory.",
        used="historic-hazards.html (popup)", length=254),
    Fld("Confidence", "SHORT", "Confidence",
        "Mapping confidence, 1 (low) to 3 (high); some inventories also use 5 and 8.",
        used="historic-hazards.html (popup); score_exposure.py (fetched with the records)"),
    Fld("Inventory", "TEXT", "Source inventory", "State inventory the record comes from (CGS or NBMG in the basin).",
        used="historic-hazards.html (popup); score_exposure.py (logged for dropped mapping units)", length=254),
    Fld("Info_Sourc", "TEXT", "Reference", "Reference for the mapping.", used="historic-hazards.html (popup)",
        length=254),
]
RECORD_FIELDS["Landslide_Inventory_Polygons"] = LANDSLIDE_RECORD_FIELDS
RECORD_FIELDS["Landslide_Inventory_Points"] = LANDSLIDE_RECORD_FIELDS


# ----------------------------------------------------------------------------------------
# the two metadata tables (described in the dictionary like any other table)

DICT_FIELDS = [
    Fld("dataset", "TEXT", "Dataset", "Feature class or table the field belongs to.", length=64),
    Fld("feature_dataset", "TEXT", "Feature dataset", "Feature dataset that holds the layer; blank for tables.",
        length=32),
    Fld("field_order", "SHORT", "Field order", "Position of the field in the dataset."),
    Fld("field_name", "TEXT", "Field name", "Field name as stored.", length=64),
    Fld("alias", "TEXT", "Alias", "Field alias as stored.", length=128),
    Fld("field_type", "TEXT", "Field type", "Geodatabase field type.",
        values="OID, Geometry, Text, Short, Long, Double, Date", length=16),
    Fld("field_length", "SHORT", "Length", "Maximum length of a text field; null for other types."),
    Fld("units", "TEXT", "Units", "Units of measure; blank for codes and text.", length=60),
    Fld("description", "TEXT", "Description", "What the field holds and how it is calculated.", length=2000),
    Fld("valid_values", "TEXT", "Valid values", "Allowed values, codes, or expected range.", length=600),
    Fld("source", "TEXT", "Source", "Dataset and field the value comes from.", length=300),
    Fld("transformation", "TEXT", "Transformation",
        "What the build did to the source value (copied, joined, renamed, cleaned, or calculated).", length=600),
    Fld("used_by", "TEXT", "Used by", "Pages (html/) and scripts (scripts/) that read the field, or the score it feeds.",
        length=800),
    Fld("row_count", "LONG", "Rows", "Rows in the dataset at build time."),
    Fld("null_count", "LONG", "Nulls", "Rows where the field is null."),
    Fld("distinct_count", "LONG", "Distinct values", "Number of distinct values, not counting null."),
    Fld("min_value", "TEXT", "Minimum", "Lowest value, for numbers and dates.", length=64),
    Fld("max_value", "TEXT", "Maximum", "Highest value, for numbers and dates.", length=64),
    Fld("top_values", "TEXT", "Value counts",
        "Count of each value when there are 25 or fewer; 'unique' when no value repeats.", length=600),
]
CATALOG_FIELDS = [
    Fld("dataset", "TEXT", "Dataset", "Feature class or table name.", length=64),
    Fld("feature_dataset", "TEXT", "Feature dataset", "Feature dataset that holds it; blank for tables.", length=32),
    Fld("dataset_type", "TEXT", "Type", "Feature class or table.", length=16),
    Fld("geometry_type", "TEXT", "Geometry", "Point, polyline, or polygon; blank for tables.", length=16),
    Fld("row_count", "LONG", "Rows", "Rows at build time."),
    Fld("field_count", "SHORT", "Fields", "Attribute fields, not counting OBJECTID, geometry, Shape_Length, or Shape_Area."),
    Fld("title", "TEXT", "Title", "Short title.", length=120),
    Fld("description", "TEXT", "Description", "What the dataset holds and how the assessment uses it.", length=2000),
    Fld("source", "TEXT", "Source", "Where the rows come from.", length=1000),
    Fld("row_filter", "TEXT", "Rows kept", "Which source rows are kept.", length=800),
    Fld("primary_key", "TEXT", "Key", "Field that identifies a row.", length=64),
    Fld("relates_to", "TEXT", "Relates to", "Joins and relationship classes.", length=600),
    Fld("used_by", "TEXT", "Used by", "Pages and scripts that read the dataset.", length=800),
    Fld("spatial_reference", "TEXT", "Spatial reference", "Coordinate system; blank for tables.", length=60),
    Fld("built", "DATE", "Built", "Date the dataset was written."),
]


# ----------------------------------------------------------------------------------------
# datasets

def datasets(cfg: dict, restricted: bool) -> list:
    a, ex = cfg["assets"], cfg["exposure"]
    gdb, hz = Path(cfg["paths"]["analysis_gdb"]).name, Path(ex["hazards_gdb"]).name
    rows_public = ("NDOT rows are left out because they are restricted, as in the published results." if not restricted
                   else "All jurisdictions, including NDOT. Restricted: keep on TRPA storage.")
    flood_used = ("score_exposure.py (FL-C, FL-B, FL-R, FL-AT, and FL-TC exposure); results.html (Flooding tab surface, "
                  "published as flood_surface.geojson)")
    hist = "Scores are for the historical horizon."
    return [
        Dataset("Roads", "Assets", "POLYLINE", "Street links with criticality and road vulnerability scores",
                f"Every link in the clean street network, with the criticality fields and the exposure and vulnerability "
                f"scores for the five road pairs (FL-R, LS-R, WF-R, DF-R, and AV-R). The analysis geodatabase keeps these "
                f"in the street layer and six score tables; here they are joined on src_objectid, one row per link. "
                f"{hist}",
                f"{Path(a['streets_gdb']).name}/{a['streets_fc']} (built by scripts/Streets_Network_Clean.ipynb), joined "
                f"with {gdb}/Vulnerability_roads and the Exposure_<hazard>_roads tables on src_objectid", SNTC,
                "All 18,285 links.", "src_objectid",
                "Culverts.parent_segment_id and Bridges.parent_segment_id (relationship classes Road_has_Culverts and "
                "Road_has_Bridges)",
                "results.html (every tab); criticality-index.html; od-services-index.html (via roads_od.json); "
                "workshop-feedback.html (same links, read from the PROTECT_VA hosted layer); scoring-rubrics.html "
                "(matrix)", roads_fields()),
        Dataset("Culverts", "Assets", "POINT", "Culverts with their profile and scores",
                f"Every culvert scored for FL-C, LS-C, and DF-C. These are culverts on a street link that are not part "
                f"of an NBI culvert-type structure. Fields come from the agency inventories, the culvert profile "
                f"(drainage, flow, capacity, condition), and the pair scores. Text is trimmed and blanks are stored as "
                f"null. {hist}",
                f"{gdb}/{a['culverts_fc']}, written by scripts/load_culverts_gdb.py, culvert_profile.py, "
                f"score_exposure.py, and score_vulnerability.py", a["culverts_fc"],
                f"Culverts with scored = 1. {rows_public} Stormwater pipes, culverts more than 50 m from a street link, "
                f"and inventory points within 25 m of an NBI culvert-type structure are not included.",
                "culvert_id",
                "CulvertCondition.culvert_id (Culvert_has_Condition, one to many); CulvertWatersheds.crossing_id "
                "(Watershed_has_Culverts); Roads.src_objectid via parent_segment_id (Road_has_Culverts)",
                "results.html (Overview, Flooding, Landslide, and Debris flow tabs); workshop-feedback.html; "
                "scoring-rubrics.html; tahoe-precip-events.html (its own embedded copy)", culverts_fields()),
        Dataset("CulvertCondition", "", "", "Culvert inspection records",
                "One row per inspection of a culvert in this geodatabase. Culverts.cond_class comes from the latest "
                "inspection (rubric 2.5).", f"{gdb}/{a['condition_table']}", a["condition_table"],
                f"Inspections of the culverts in this geodatabase. {rows_public}", "culvert_id and inspection_date",
                "Culverts.culvert_id (Culvert_has_Condition)",
                "culvert_profile.py (cond_class, blockage); tahoe-precip-events.html (popup)", CONDITION_FIELDS),
        Dataset("CulvertWatersheds", "Assets", "POLYGON", "Drainage area of each culvert crossing",
                "For each crossing, the ground that drains to it without passing through another crossing first. "
                "Delineated by scripts/culvert_profile.py on the 2 m lidar DEM, breached at the inventory culverts. A "
                "crossing's full watershed is its own polygon plus every polygon upstream (follow "
                "downstream_crossing_id); contrib_area_ac gives the total.",
                f"{gdb}/CulvertWatersheds_inc, joined with {gdb}/CulvertCrossings on crossing_id",
                "CulvertWatersheds_inc",
                ("Crossings with no restricted-jurisdiction culvert (CulvertCrossings.restricted = 0). The 143 "
                 "downstream links that point to a withheld crossing are set to null." if not restricted
                 else "All crossings."),
                "crossing_id", "Culverts.crossing_id (Watershed_has_Culverts)",
                "score_exposure.py (culvert exposure, highest class in the watershed); results.html (drainage area on "
                "click, published per crossing under watersheds/)", WATERSHED_FIELDS),
        Dataset("Bridges", "Assets", "POINT", "NBI bridges and large culverts with their scores",
                f"The 40 National Bridge Inventory structures inside the TRPA boundary (five are large culverts), with "
                f"the NBI items the rubrics use and the FL-B, LS-B, and DF-B scores. {hist}",
                f"{gdb}/{a['bridges_fc']}, built by scripts/build_bridges.py from {a['nbi_basin_fc']} and scored by "
                f"score_exposure.py and score_vulnerability.py", a["bridges_fc"], "All 40 structures.", "bridge_id",
                "Roads.src_objectid via parent_segment_id (Road_has_Bridges)",
                "results.html (Overview, Flooding, Landslide, and Debris flow tabs); workshop-feedback.html; "
                "scoring-rubrics.html; make_pro_maps.py", bridges_fields()),
        Dataset("ActiveTransportation", "Assets", "POLYLINE", "Existing paths and bike facilities with their scores",
                f"Existing active transportation facilities with their FL-AT and WF-AT scores. Geometry and names come "
                f"from the TRPA Transportation service, the same layer the scoring used. {hist}",
                f"{ex['active_transport_layer']}, joined with {gdb}/Vulnerability_active_transport and "
                f"Exposure_wildfire_active_transport on at_id", "Vulnerability_active_transport",
                "The 216 facilities that have scores.", "at_id", "",
                "results.html (Overview and Wildfire path layers); workshop-feedback.html (asset cards)", paths_fields()),
        Dataset("TransitHubs", "Assets", "POINT", "Transit hubs with their scores",
                f"The eight transit hubs, with their FL-TC and WF-TC scores. {hist}",
                f"{ex['transit_centers_layer']}, joined with {gdb}/Vulnerability_transit_centers and "
                f"Exposure_wildfire_transit_centers on tc_id", "Vulnerability_transit_centers", "All eight hubs.",
                "tc_id", "", "results.html (Overview and Wildfire hub layers)", hubs_fields()),
        Dataset("Hazard_Flood_Class", "HazardSurfaces", "POLYGON", "Flood exposure classes",
                "The flood surface every flood pair is scored against. FEMA 1 percent annual chance zones are class 3; "
                "the 0.2 percent zone and a 10 m buffer around lidar-derived streams are class 2. The lake's own 1 "
                "percent stillwater zone (FEMA polygons more than half on a water body over 1 km2) is left out, since "
                "lake flooding belongs to the proposed high lake level pair, which has not been adopted. Where classes "
                "overlap, the higher one is kept, and polygons are dissolved by class and split into single parts.",
                f"{hz}/{ex['flood']['class_fc']}, built by score_exposure.py --hazard flood --build from "
                f"Streams_and_Flood_Zone layers 0 and 1", ex["flood"]["class_fc"], "All polygons.", "", "", flood_used,
                surface_fields("Flood class. Where classes overlap, the higher one is kept.",
                               "2 (0.2 percent zone or within 10 m of a mapped stream), 3 (1 percent zone)", flood_used)),
        Dataset("Hazard_Wildfire_BurnProb", "HazardSurfaces", "POLYGON", "Annual burn probability classes (wildfire E1)",
                "Pyrologix 2022 annual burn probability (Sierra Nevada Regional Resource Kit, 30 m), classed on the "
                "draft methodology's breaks: 3 over 1 percent, 2 over 0.5 to 1 percent, and 1 over 0 to 0.5 percent. "
                "Clipped to the basin's bounding box plus about 500 m.",
                f"{hz}/{ex['wildfire']['bp_fc']}, built by score_exposure.py --hazard wildfire --build",
                ex["wildfire"]["bp_fc"], "All polygons.", "", "",
                "score_exposure.py (WF-R, WF-AT, and WF-TC E1); results.html (Wildfire tab surface and 300 ft "
                "footprint)",
                surface_fields("Annual burn probability class.",
                               "1 (over 0 to 0.5 percent), 2 (over 0.5 to 1 percent), 3 (over 1 percent)",
                               "score_exposure.py (wildfire E1); results.html (Wildfire tab surface)")),
        Dataset("Hazard_Wildfire_Severity", "HazardSurfaces", "POLYGON",
                "Fire severity classes (wildfire E2, debris-flow E3)",
                "TRPA's most-likely fire severity, which combines the Regional Resource Kit 2023 severity probabilities "
                "into one class: 3 High, 2 Moderate, and 1 Low. Used for wildfire E2 until the flame length data under "
                "contract arrives, and in place of predicted soil burn severity for debris-flow E3.",
                f"{hz}/{ex['wildfire']['e2_fc']}, built by score_exposure.py --hazard wildfire --build from "
                f"Fire/MapServer/3", ex["wildfire"]["e2_fc"], "All polygons.", "", "",
                "score_exposure.py (wildfire E2, debris-flow E3); results.html (Wildfire tab surface and 300 ft "
                "footprint)",
                surface_fields("Most-likely fire severity class.", "1 (Low), 2 (Moderate), 3 (High)",
                               "score_exposure.py (wildfire E2, debris-flow E3); results.html (Wildfire tab surface)")),
        Dataset("Hazard_Landslide_Class", "HazardSurfaces", "POLYGON", "Landslide susceptibility classes (landslide E1)",
                "USGS 2024 landslide susceptibility (Mirus and others, doi 10.5066/P13KAGU3), which counts the "
                "landslide-prone 10 m cells in each 90 m cell. Classed on the share of the cell that is prone: 3 over "
                "80 percent, 2 over 60, and 1 over 40. Recorded landslides (USGS inventory polygons under 10 km2, and "
                "points buffered 50 m) are class 3.",
                f"{hz}/{ex['landslide']['class_fc']}, built by score_exposure.py --hazard landslide --build",
                ex["landslide"]["class_fc"], "All polygons.", "", "",
                "score_exposure.py (LS-C, LS-B, and LS-R E1); results.html (Landslide tab surface)",
                surface_fields("Landslide susceptibility class.",
                               "1 (over 40 to 60 percent of the 90 m cell landslide-prone), 2 (over 60 to 80 percent), "
                               "3 (over 80 percent, or a recorded landslide)",
                               "score_exposure.py (landslide E1); results.html (Landslide tab surface)",
                               label_how=LANDSLIDE_LABEL_HOW)),
        Dataset("Hazard_DebrisFlow_Slope", "HazardSurfaces", "POLYGON", "Upslope steepness scores (debris-flow E1)",
                "Average slope of the ground upslope of each 2 m cell (slope-weighted flow accumulation divided by flow "
                "accumulation), averaged to 30 m and scored on the draft methodology's half-point breaks: 3 over 30 "
                "percent, 2.5 over 25, 2 over 20, 1.5 over 15, 1 over 10, and 0.5 over 5. Ground that scores 0 is not "
                "stored.",
                f"{hz}/{ex['debris_flow']['slope_fc']}, built by surfaces_dfav.py through score_exposure.py --hazard "
                f"debris_flow --build", ex["debris_flow"]["slope_fc"], "All polygons.", "", "",
                "score_exposure.py (DF-R and DF-B E1; culverts use their own basin slope instead)",
                surface_fields("Upslope steepness score.", "0.5 to 3 in half points",
                               "score_exposure.py (DF-R and DF-B E1)", half_points=True, label=False)),
        Dataset("Hazard_DebrisFlow_Area", "HazardSurfaces", "POLYGON", "Drainage size scores (debris-flow E2)",
                "Drainage area at each 30 m cell (the largest 2 m flow accumulation in it), scored on the draft "
                "methodology's breaks, with smaller drainages scoring higher: 3 under 0.25 sq mi, 2.5 up to 0.5, 2 up "
                "to 1, 1.5 up to 2, 1 up to 3, and 0.5 up to 5. Ground draining more than 5 sq mi scores 0 and is not "
                "stored.",
                f"{hz}/{ex['debris_flow']['area_fc']}, built by surfaces_dfav.py", ex["debris_flow"]["area_fc"],
                "All polygons.", "", "", "score_exposure.py (DF-R and DF-B E2, at the largest drainage area touched)",
                surface_fields("Drainage size score.", "0.5 to 3 in half points",
                               "score_exposure.py (DF-R and DF-B E2)", half_points=True, label=False)),
        Dataset("Hazard_Avalanche_Cells", "HazardSurfaces", "POLYGON", "Avalanche terrain by slope tier and elevation band",
                "Slope tiers on the 10 m grid, by 20 m elevation band. AV-R takes each link's uphill tier from this "
                "surface (decision 17). Each polygon is a group of adjacent cells with the same tier and band.",
                f"{hz}/{ex['avalanche']['cells_fc']}, built by surfaces_dfav.py from the 2 m lidar DEM",
                ex["avalanche"]["cells_fc"], "All polygons.", "", "", "score_exposure.py (AV-R, through surfaces_dfav.py)",
                AVALANCHE_FIELDS),
        Dataset("Avalanche_Zones", "HazardSources", "POLYGON", "TRPA avalanche zones",
                "TRPA's mapped avalanche zones. AV-R uses them as the avalanche record (decision 18); accident databases "
                "are not used.",
                ex["avalanche"]["zones_layer"], "Avalanche_Zones/MapServer/0", "All zones.", "", "",
                "score_exposure.py (av_record, zones within 1,000 ft); results.html (Avalanche tab zones)",
                RECORD_FIELDS["Avalanche_Zones"]),
        Dataset("FEMA_Flood_Zones", "HazardSources", "POLYGON", "FEMA flood zones",
                "FEMA flood hazard zones. They are the source of flood classes 2 and 3 and of the street flood flags. "
                "Unlike Hazard_Flood_Class, this layer keeps the lake's stillwater zone.",
                ex["flood"]["zones_layer"], "Streams_and_Flood_Zone/MapServer/0", "All polygons.", "", "",
                "score_exposure.py (flood class); Streets_Network_Clean.ipynb (Roads.in_flood_zone and "
                "in_flood_zone_100)", RECORD_FIELDS["FEMA_Flood_Zones"]),
        Dataset("Landslide_Inventory_Polygons", "HazardSources", "POLYGON", "Recorded landslides (USGS inventory polygons)",
                "Mapped landslide deposits from the USGS US Landslide Inventory, which in the basin draws on the "
                "California Geological Survey and the Nevada Bureau of Mines and Geology. They are class 3 in "
                "Hazard_Landslide_Class.",
                ex["landslide"]["recorded_polys"], "US_Landslide_poly_v2/FeatureServer/12",
                f"Polygons in the basin's bounding box (the same query the scoring used), except those over "
                f"{ex['landslide'].get('recorded_max_area_km2', 10)} km2, which are mapping units rather than single "
                f"landslides.", "USGS_ID", "",
                "score_exposure.py (landslide class 3); historic-hazards.html (map, popup)",
                RECORD_FIELDS["Landslide_Inventory_Polygons"]),
        Dataset("Landslide_Inventory_Points", "HazardSources", "POINT", "Recorded landslides (USGS inventory points)",
                "Landslide points from the USGS US Landslide Inventory. Buffered 50 m, they are class 3 in "
                "Hazard_Landslide_Class.",
                ex["landslide"]["recorded_points"], "US_Landslide_point_v2/FeatureServer/11",
                "Points in the basin's bounding box (the same query the scoring used).", "USGS_ID", "",
                "score_exposure.py (landslide class 3); historic-hazards.html (map, popup)",
                RECORD_FIELDS["Landslide_Inventory_Points"]),
        Dataset("Fire_Perimeters", "HazardSources", "POLYGON", "Historic fire perimeters (CAL FIRE)",
                "CAL FIRE fire perimeters that touch the TRPA boundary. The data covers California only, so fires on "
                "the Nevada side are missing. Shown for context; not used in scoring.",
                cfg["curated"]["fire_perimeters_layer"], "California_Historic_Fire_Perimeters/FeatureServer/0",
                "Perimeters that intersect the TRPA boundary, matching the count on the Historic Hazards page.", "", "",
                "historic-hazards.html (map, popup, table); workshop-feedback.html (context layer)",
                RECORD_FIELDS["Fire_Perimeters"]),
        Dataset("Earthquakes", "HazardSources", "POINT", "Historic earthquakes (USGS ComCat)",
                "Earthquakes of magnitude 2.5 or more since 1900, in the area the Historic Hazards page queries. Shown "
                "for context; not used in scoring.", cfg["curated"]["earthquakes_url"], "ComCat",
                "Magnitude 2.5 or more, from 1900 to the build date, latitude 38.7 to 39.4, longitude -120.3 to -119.8.",
                "event_id", "", "historic-hazards.html (map, popup)", RECORD_FIELDS["Earthquakes"]),
    ]


# ----------------------------------------------------------------------------------------
# builders: each returns a (Geo)DataFrame with the spec's columns (or a Copy)

def _read(gdb: str, layer: str, columns: list | None = None, geometry: bool = True):
    import pyogrio
    return pyogrio.read_dataframe(gdb, layer=layer, columns=columns, read_geometry=geometry)


def _int_key(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def _src_cols(ds: Dataset, skip=()) -> list:
    """Source column names for the fields read straight from the dataset's own source layer."""
    return [f.name for f in ds.fields if not f.src and f.name not in skip]


def _road_c_class(ctx) -> pd.Series:
    """Roads.C_class by src_objectid: from this run, or from the curated Roads when resuming."""
    if "road_c_class" not in ctx:
        r = _read(ctx["out_gdb"], "Roads", columns=["src_objectid", "C_class"], geometry=False)
        ctx["road_c_class"] = r.assign(src_objectid=_int_key(r["src_objectid"])).set_index("src_objectid")["C_class"]
    return ctx["road_c_class"]


def _culvert_ids(ctx) -> set:
    """culvert_id values of the curated Culverts: from this run, or from the geodatabase when resuming."""
    if "culvert_ids" not in ctx:
        ctx["culvert_ids"] = set(_read(ctx["out_gdb"], "Culverts", columns=["culvert_id"], geometry=False)["culvert_id"])
    return ctx["culvert_ids"]


def build_roads(ds, cfg, ctx, log):
    import shapely
    a = cfg["assets"]
    gdb, key = cfg["paths"]["analysis_gdb"], a["streets_key"]
    st = _read(a["streets_gdb"], a["streets_fc"], columns=_src_cols(ds)).to_crs(target_crs(cfg))
    st["geometry"] = shapely.force_2d(st.geometry.values)
    st[key] = _int_key(st[key])

    def table(name, cols, rename=None):
        t = _read(gdb, name, columns=[key] + cols, geometry=False)
        t[key] = _int_key(t[key])
        if t[key].duplicated().any():
            raise SystemExit(f"{name}: duplicate {key}")
        return t.rename(columns=rename or {})

    vr = table("Vulnerability_roads", ["seg_len_m", "C_class", "criticality_pctl", "V_FLR_hist", "V_LSR_hist", "V_WFR_hist",
                                       "V_DFR_hist", "V_AVR_hist", "V_max", "V_max_pair", "V_class", "V_max_all",
                                       "V_max_all_pair", "V_class_all"])
    chk = st[[key, "criticality_pctl"]].merge(vr[[key, "criticality_pctl"]], on=key, suffixes=("", "_scored"))
    stale = int(((chk["criticality_pctl"] - chk["criticality_pctl_scored"]).abs() > 0.005).sum())
    if stale:
        log.warning(f"{stale} links whose criticality_pctl changed since the roads were scored; C_class comes from the scoring")
    r = st.merge(vr.drop(columns="criticality_pctl"), on=key, how="left", validate="one_to_one")
    lp = lambda p, ks: {f"len_pct_c{k}": f"{p}_len_pct_c{k}" for k in ks}
    import pyogrio
    df_e3 = "E_DFR_e3" if "E_DFR_e3" in pyogrio.read_info(gdb, layer="Exposure_debris_flow_roads")["fields"] else "E_e3"
    for name, cols, ren in (
            ("Exposure_flood_roads", ["E_FLR_hist", "len_pct_c2", "len_pct_c3"], lp("FLR", (2, 3))),
            ("Exposure_landslide_roads", ["E_LSR_hist", "E_LSR_e1", "E_LSR_e2", "len_pct_c1", "len_pct_c2", "len_pct_c3"],
             lp("LSR", (1, 2, 3))),
            ("Exposure_wildfire_roads", ["E_WFR_hist", "E_WFR_e1", "E_WFR_e2", "len_pct_c1", "len_pct_c2", "len_pct_c3"],
             lp("WFR", (1, 2, 3))),
            ("Exposure_debris_flow_roads", ["E_DFR_hist", "E_DFR_e1", "E_DFR_e2", df_e3], {"E_e3": "E_DFR_e3"}),
            ("Exposure_avalanche_roads", ["E_AVR_hist", "av_tier", "av_record", "uphill_ha"], None)):
        r = r.merge(table(name, cols, ren), on=key, how="left", validate="one_to_one")
    missing = int(r["V_class"].isna().sum())
    if missing:
        log.warning(f"{missing} links without a row in Vulnerability_roads")
    ctx["road_c_class"] = r.set_index(key)["C_class"]
    return gpd.GeoDataFrame(r, geometry="geometry", crs=st.crs)


def build_culverts(ds, cfg, ctx, log):
    a, p = cfg["assets"], cfg["profile"]
    cols = _src_cols(ds, skip={"C_class"}) + ["scored", "feature_type"]
    cul = _read(cfg["paths"]["analysis_gdb"], a["culverts_fc"], columns=cols).to_crs(target_crs(cfg))
    n0 = len(cul)
    mixed = restricted_crossings(cul, ctx["restricted"]) if ctx["restricted"] else set()
    cul = cul[cul["scored"] == 1]
    if ctx["restricted"]:
        drop = cul["jurisdiction"].isin(ctx["restricted"])
        log.info(f"{int(drop.sum())} scored restricted culverts excluded")
        cul = withhold_pooled(cul[~drop].copy(), mixed, log)
    log.info(f"Culverts: {len(cul)} of {n0} rows kept (scored, public)" if ctx["restricted"] else
             f"Culverts: {len(cul)} of {n0} rows kept (scored)")
    from culvert_profile import clean_span_rise
    cul["span_in"], cul["rise_in"] = clean_span_rise(cul, p)
    v = pd.to_numeric(cul["length_ft"], errors="coerce")
    cul["length_ft"] = v.where(v > 0)
    v = pd.to_numeric(cul["install_year"], errors="coerce")
    cul["install_year"] = v.where(v >= 1900)
    cul["parent_segment_id"] = _int_key(cul["parent_segment_id"])
    cul["C_class"] = cul["parent_segment_id"].map(_road_c_class(ctx)).astype("Int64")
    ctx["culvert_ids"] = set(cul["culvert_id"])
    return cul


def build_condition(ds, cfg, ctx, log):
    c = _read(cfg["paths"]["analysis_gdb"], cfg["assets"]["condition_table"], columns=_src_cols(ds), geometry=False)
    n0 = len(c)
    c = c[c["culvert_id"].isin(_culvert_ids(ctx))].sort_values(["culvert_id", "inspection_date"])
    log.info(f"CulvertCondition: {len(c)} of {n0} inspections belong to curated culverts")
    return c


def build_watersheds(ds, cfg, ctx, log):
    gdb = cfg["paths"]["analysis_gdb"]
    ws = _read(gdb, "CulvertWatersheds_inc", columns=["crossing_id", "downstream_crossing_id"]).to_crs(target_crs(cfg))
    xt = _read(gdb, "CulvertCrossings", columns=["crossing_id", "restricted", "contrib_area_ac"], geometry=False)
    keep = xt if not ctx["restricted"] else xt[xt["restricted"] == 0]
    ws = ws[ws["crossing_id"].isin(keep["crossing_id"])].copy()
    cut = ws["downstream_crossing_id"].notna() & ~ws["downstream_crossing_id"].isin(ws["crossing_id"])
    ws.loc[cut, "downstream_crossing_id"] = None
    log.info(f"CulvertWatersheds: {len(ws)} of {len(xt)} crossings kept; {int(cut.sum())} downstream links to a crossing not "
             f"in the layer nulled")
    ws["area_ac"] = (ws.geometry.area / SQM_PER_ACRE).round(2)
    ws = ws.merge(keep[["crossing_id", "contrib_area_ac"]], on="crossing_id", how="left", validate="one_to_one")
    return gpd.GeoDataFrame(ws, geometry="geometry", crs=target_crs(cfg))


def build_bridges(ds, cfg, ctx, log):
    br = _read(cfg["paths"]["analysis_gdb"], cfg["assets"]["bridges_fc"], columns=_src_cols(ds, skip={"C_class"}))
    br = br.to_crs(target_crs(cfg))
    br["parent_segment_id"] = _int_key(br["parent_segment_id"])
    br["C_class"] = br["parent_segment_id"].map(_road_c_class(ctx)).astype("Int64")
    return br


def _scores(gdb: str, key: str, vtable: str, etable: str, ecols: list, vcols: list) -> pd.DataFrame:
    v = _read(gdb, vtable, columns=[key] + [c for c in vcols if c != key], geometry=False)
    e = _read(gdb, etable, columns=[key] + [c for c in ecols if c != key], geometry=False)
    for t in (v, e):
        t[key] = _int_key(t[key])
    return v.merge(e, on=key, how="left", validate="one_to_one")


def build_paths(ds, cfg, ctx, log):
    from score_exposure import fetch_with_fields
    ex, gdb = cfg["exposure"], cfg["paths"]["analysis_gdb"]
    k = ex.get("active_transport_key", "OBJECTID")
    g = fetch_with_fields(ex["active_transport_layer"], [k, "NAME", "CLASS", "MAINT_JURS", "MILES"], target_crs(cfg), log)
    g["at_id"] = _int_key(g[k])
    g = g.rename(columns={"NAME": "name", "CLASS": "class", "MAINT_JURS": "maint_jurs", "MILES": "miles"})
    vcols = [f.name for f in ds.fields if f.src.startswith("Vulnerability_active_transport")]
    ecols = [f.name for f in ds.fields if f.src.startswith("Exposure_wildfire_active_transport")]
    s = _scores(gdb, "at_id", "Vulnerability_active_transport", "Exposure_wildfire_active_transport", ecols, vcols)
    r = g.merge(s, on="at_id", how="inner", validate="one_to_one")
    log.info(f"ActiveTransportation: {len(r)} facilities with scores ({len(g)} in the service, {len(s)} scored)")
    return gpd.GeoDataFrame(r, geometry="geometry", crs=target_crs(cfg))


def build_hubs(ds, cfg, ctx, log):
    from score_exposure import fetch_with_fields
    ex, gdb = cfg["exposure"], cfg["paths"]["analysis_gdb"]
    k = ex.get("transit_centers_key", "OBJECTID")
    g = fetch_with_fields(ex["transit_centers_layer"], [k], target_crs(cfg), log)
    g["tc_id"] = _int_key(g[k])
    vcols = [f.name for f in ds.fields if f.src.startswith("Vulnerability_transit_centers")]
    ecols = [f.name for f in ds.fields if f.src.startswith("Exposure_wildfire_transit_centers")]
    s = _scores(gdb, "tc_id", "Vulnerability_transit_centers", "Exposure_wildfire_transit_centers", ecols, vcols)
    r = g.merge(s, on="tc_id", how="inner", validate="one_to_one")
    log.info(f"TransitHubs: {len(r)} hubs with scores ({len(g)} in the service, {len(s)} scored)")
    return gpd.GeoDataFrame(r, geometry="geometry", crs=target_crs(cfg))


def build_surface(ds, cfg, ctx, log):
    from score_exposure import landslide_labels
    ls = cfg["exposure"]["landslide"]
    return Copy(f"{cfg['exposure']['hazards_gdb']}\\{ds.src_layer}",
                labels=landslide_labels(ls) if ds.src_layer == ls["class_fc"] else None)


def build_avalanche_zones(ds, cfg, ctx, log):
    from score_exposure import fetch_with_fields
    return fetch_with_fields(cfg["exposure"]["avalanche"]["zones_layer"], ["Name", "Frequency"], target_crs(cfg), log)


def build_fema(ds, cfg, ctx, log):
    from score_exposure import fetch_with_fields
    fl = cfg["exposure"]["flood"]
    return fetch_with_fields(fl["zones_layer"], [fl["zone_field"], fl["year_field"]], target_crs(cfg), log)


def _basin_bbox(cfg, ctx, log):
    if "basin" not in ctx:
        ctx["basin"] = fetch_basin(cfg, log)
    return ctx["basin"].to_crs("EPSG:4326").total_bounds


def build_landslide(ds, cfg, ctx, log):
    from score_exposure import fetch_in_bbox
    ls = cfg["exposure"]["landslide"]
    url = ls["recorded_polys"] if ds.geom == "POLYGON" else ls["recorded_points"]
    g = fetch_in_bbox(url, ["OBJECTID"] + _src_cols(ds), _basin_bbox(cfg, ctx, log), target_crs(cfg), log,
                      where=str(ls.get("recorded_where") or "1=1"))
    if ds.geom == "POLYGON":
        cap = float(ls.get("recorded_max_area_km2", 10)) * SQM_PER_KM2
        big = g.area > cap
        log.info(f"{int(big.sum())} inventory polygon(s) over {cap / SQM_PER_KM2:g} km2 dropped (mapping units)")
        g = g[~big]
    return g


def _get_json(url: str, params: dict, log, tries: int = 4) -> dict:
    """GET with retries on gateway errors and timeouts (the hosted services time out on large pages)."""
    import time
    import requests
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=300)
            if r.status_code < 500:
                r.raise_for_status()
                return r.json()
            err = f"HTTP {r.status_code}"
        except (requests.Timeout, requests.ConnectionError) as e:
            err = type(e).__name__
        log.warning(f"{url}: {err}; retry {i + 1} of {tries - 1}" if i < tries - 1 else f"{url}: {err}; giving up")
        time.sleep(10 * (i + 1))
    raise SystemExit(f"{url} did not answer after {tries} tries")


def _fetch_by_ids(url: str, fields: list, bbox4326, crs, log, chunk: int = 25) -> gpd.GeoDataFrame:
    """Features in a WGS84 envelope, fetched by object id in small batches: the ids first, then the features, so
    no single request carries a page of large polygons."""
    env = ",".join(f"{v:.6f}" for v in bbox4326)
    ids = _get_json(f"{url}/query", {"where": "1=1", "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                                     "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true", "f": "json"},
                    log).get("objectIds") or []
    frames = []
    for i in range(0, len(ids), chunk):
        gj = _get_json(f"{url}/query", {"objectIds": ",".join(str(v) for v in ids[i:i + chunk]), "outFields": ",".join(fields),
                                        "returnGeometry": "true", "f": "geojson"}, log)
        if gj.get("features"):
            frames.append(gpd.GeoDataFrame.from_features(gj["features"], crs="EPSG:4326"))
    out = pd.concat(frames, ignore_index=True) if frames else gpd.GeoDataFrame(columns=fields, geometry=[], crs="EPSG:4326")
    log.info(f"{len(out)} of {len(ids)} features from {url} in the basin box")
    return gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:4326").to_crs(crs)


def build_fires(ds, cfg, ctx, log):
    g = _fetch_by_ids(cfg["curated"]["fire_perimeters_layer"], ["OBJECTID"] + _src_cols(ds), _basin_bbox(cfg, ctx, log),
                      target_crs(cfg), log)
    basin = ctx["basin"].geometry.union_all()
    g = g[g.intersects(basin)].copy()
    for c in ("ALARM_DATE", "CONT_DATE"):
        g[c] = pd.to_datetime(pd.to_numeric(g[c], errors="coerce"), unit="ms")
    log.info(f"Fire_Perimeters: {len(g)} perimeters touch the TRPA boundary")
    return g.sort_values(["YEAR_", "FIRE_NAME"], ascending=[False, True])


def build_quakes(ds, cfg, ctx, log):
    cu = cfg["curated"]
    lat0, lat1, lon0, lon1 = cu["earthquakes_box"]
    params = {"format": "geojson", "starttime": "1900-01-01", "minmagnitude": cu.get("earthquakes_min_mag", 2.5),
              "minlatitude": lat0, "maxlatitude": lat1, "minlongitude": lon0, "maxlongitude": lon1, "orderby": "time-asc"}
    gj = _get_json(cu["earthquakes_url"], params, log)
    feats = gj.get("features", [])
    g = gpd.GeoDataFrame({"event_id": [f["id"] for f in feats],
                          "mag": [f["properties"].get("mag") for f in feats],
                          "place": [f["properties"].get("place") for f in feats],
                          "event_time": pd.to_datetime([f["properties"].get("time") for f in feats], unit="ms")},
                         geometry=gpd.points_from_xy([f["geometry"]["coordinates"][0] for f in feats],
                                                     [f["geometry"]["coordinates"][1] for f in feats]), crs="EPSG:4326")
    log.info(f"Earthquakes: {len(g)} events from ComCat")
    return g.to_crs(target_crs(cfg))


BUILDERS = {"Roads": build_roads, "Culverts": build_culverts, "CulvertCondition": build_condition,
            "CulvertWatersheds": build_watersheds, "Bridges": build_bridges, "ActiveTransportation": build_paths,
            "TransitHubs": build_hubs, "Avalanche_Zones": build_avalanche_zones, "FEMA_Flood_Zones": build_fema,
            "Landslide_Inventory_Polygons": build_landslide, "Landslide_Inventory_Points": build_landslide,
            "Fire_Perimeters": build_fires, "Earthquakes": build_quakes}


# ----------------------------------------------------------------------------------------
# writing

def _path(gdb: str, ds: Dataset) -> str:
    return f"{gdb}\\{ds.group}\\{ds.name}" if ds.group else f"{gdb}\\{ds.name}"


def _tidy_text(df: pd.DataFrame, fields: list) -> pd.DataFrame:
    """Trim text values and store blank strings as null."""
    for f in fields:
        if f.ftype == "TEXT" and f.name in df.columns:
            s = df[f.name]
            df[f.name] = s.where(s.isna(), s.astype(str).str.strip()).replace({"": None})
    return df


def write_rows(gdb: str, ds: Dataset, data, sr, log) -> None:
    import arcpy
    path = _path(gdb, ds)
    if isinstance(data, Copy):
        fms = arcpy.FieldMappings()
        for f in ds.fields:
            fm = arcpy.FieldMap()
            fm.addInputField(data.src, f.name)
            of = fm.outputField
            of.name, of.aliasName = f.name, f.alias
            fm.outputField = of
            fms.addFieldMap(fm)
        arcpy.conversion.ExportFeatures(data.src, path, field_mapping=fms)
        log.info(f"{ds.name}: {int(arcpy.management.GetCount(path)[0]):,} rows copied from {data.src}")
        if data.labels:
            with arcpy.da.UpdateCursor(path, ["hz_class", "label"]) as cur:
                for row in cur:
                    cur.updateRow([row[0], data.labels.get(int(row[0]), row[1])])
            log.info(f"{ds.name}: labels rewritten {data.labels}")
        return
    missing = [f.name for f in ds.fields if f.name not in data.columns]
    if missing:
        raise SystemExit(f"{ds.name}: builder did not produce {missing}")
    data = _tidy_text(data.copy(), ds.fields)
    if ds.geom:
        arcpy.management.CreateFeatureclass(f"{gdb}\\{ds.group}", ds.name, ds.geom, spatial_reference=sr)
    else:
        arcpy.management.CreateTable(gdb, ds.name)
    arcpy.management.AddFields(path, [[f.name, f.ftype, f.alias, f.length or ""] for f in ds.fields])
    cols = [f.name for f in ds.fields]
    tl = {f.name: f.length for f in ds.fields if f.ftype == "TEXT"}
    ft = {f.name: f.ftype for f in ds.fields}
    arrays = [data[c].to_numpy(dtype=object) for c in cols]
    geoms = data.geometry.to_numpy() if ds.geom else None
    with arcpy.da.InsertCursor(path, (["SHAPE@"] if ds.geom else []) + cols) as cur:
        for i in range(len(data)):
            row = [to_dt(arr[i]) if ft[c] == "DATE" else clean(arr[i], c, tl, ft[c]) for c, arr in zip(cols, arrays)]
            if ds.geom:
                g = geoms[i]
                row.insert(0, None if g is None or g.is_empty else arcpy.FromWKB(g.wkb))
            cur.insertRow(row)
    log.info(f"{ds.name}: {len(data):,} rows written")


def sync_aliases(gdb: str, sets: list, log) -> None:
    """Set the stored field aliases to the spec's, for datasets a resumed run kept from an earlier build."""
    import arcpy
    for ds in sets:
        path = _path(gdb, ds)
        stored = {f.name: f.aliasName for f in arcpy.ListFields(path)}
        stale = [f for f in ds.fields if stored.get(f.name, f.alias) != f.alias]
        try:
            for f in stale:
                arcpy.management.AlterField(path, f.name, new_field_alias=f.alias)
        except Exception as e:  # noqa: BLE001
            log.warning(f"{ds.name}: aliases not updated ({e})")
            continue
        if stale:
            log.info(f"{ds.name}: {len(stale)} field aliases updated")


def relate(gdb: str, name: str, origin: str, dest: str, pk: str, fk: str, fwd: str, back: str, log) -> None:
    import arcpy
    if arcpy.Exists(f"{gdb}\\Assets\\{name}") or arcpy.Exists(f"{gdb}\\{name}"):
        log.info(f"Relationship class {name} exists; kept")
        return
    for loc in (f"{gdb}\\Assets", gdb):
        try:
            arcpy.management.CreateRelationshipClass(origin, dest, f"{loc}\\{name}", "SIMPLE", fwd, back, "NONE",
                                                     "ONE_TO_MANY", "NONE", pk, fk)
            log.info(f"Relationship class {name} ({origin.split(chr(92))[-1]}.{pk} -> {dest.split(chr(92))[-1]}.{fk})")
            return
        except Exception as e:  # noqa: BLE001
            last = e
    log.warning(f"{name} not created: {last}")


def set_metadata(path: str, ds: Dataset, restricted_build: bool) -> None:
    from arcpy import metadata as md
    m = md.Metadata(path)
    m.title = ds.title
    m.summary = ds.desc.split(". ")[0] + "."
    m.description = f"{ds.desc}\n\nRows: {ds.rows}\n\nSource: {ds.source}\n\nUsed by: {ds.used}"
    m.tags = "PROTECT, TRPA, Lake Tahoe, vulnerability assessment, " + ("hazard" if "Hazard" in ds.group else "asset")
    m.credits = "Tahoe Regional Planning Agency, PROTECT vulnerability assessment (scripts/build_curated_gdb.py)"
    m.accessConstraints = ("Restricted: contains NDOT records under the NDOT data sharing agreement; keep on TRPA storage."
                           if restricted_build else "Internal review draft; public jurisdictions only.")
    m.save()


# ----------------------------------------------------------------------------------------
# dictionary and catalog

TYPE_NAME = {"OID": "OID", "Geometry": "Geometry", "String": "Text", "SmallInteger": "Short", "Integer": "Long",
             "BigInteger": "Long", "Double": "Double", "Single": "Double", "Date": "Date", "GlobalID": "GlobalID"}


def _fmt(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(v).date())
    if isinstance(v, (float, np.floating)):
        return str(int(v)) if float(v).is_integer() else f"{float(v):.6g}"
    return str(v)


def field_stats(s: pd.Series | None, n: int, ftype: str) -> dict:
    out = {"row_count": n, "null_count": None, "distinct_count": None, "min_value": None, "max_value": None, "top_values": None}
    if s is None:
        return out
    nn = s.dropna()
    out["null_count"] = int(n - len(nn))
    out["distinct_count"] = int(nn.nunique())
    if not len(nn):
        return out
    if ftype in ("Short", "Long", "Double") or ftype == "Date":
        out["min_value"], out["max_value"] = _fmt(nn.min()), _fmt(nn.max())
    if out["distinct_count"] == len(nn) and len(nn) > 1:
        out["top_values"] = "unique"
    elif out["distinct_count"] <= 25:
        vc = nn.value_counts().sort_index() if ftype != "Text" else nn.value_counts()
        out["top_values"] = "; ".join(f"{_fmt(k)} ({v:,})" for k, v in vc.items())[:600]
    return out


def dictionary_rows(gdb: str, sets: list, log) -> tuple[list, list]:
    import arcpy
    import pyogrio
    built = pd.Timestamp.today().normalize()
    drows, crows = [], []
    for ds in sets:
        path = _path(gdb, ds)
        afields = arcpy.ListFields(path)
        n = int(arcpy.management.GetCount(path)[0])
        df = pyogrio.read_dataframe(gdb, layer=ds.name, read_geometry=False) if n else pd.DataFrame()
        spec = {f.name: f for f in ds.fields}
        geom_word = {"POINT": "Point", "POLYLINE": "Polyline", "POLYGON": "Polygon"}.get(ds.geom, "")
        user = 0
        for i, af in enumerate(afields, 1):
            t = TYPE_NAME.get(af.type, af.type)
            row = {"dataset": ds.name, "feature_dataset": ds.group, "field_order": i, "field_name": af.name,
                   "alias": af.aliasName, "field_type": t, "field_length": af.length if t == "Text" else None}
            if af.type == "OID":
                row.update(description="Row ID assigned by the geodatabase. It changes when the geodatabase is rebuilt, so "
                                       "join on the key field instead.", source="geodatabase",
                           transformation="assigned at build time", used_by="")
                st = {"row_count": n, "null_count": 0, "distinct_count": n, "min_value": "1" if n else None,
                      "max_value": str(n) if n else None, "top_values": "unique"}
            elif af.type == "Geometry":
                row.update(description=f"{geom_word} geometry, NAD 1983 UTM Zone 10N (EPSG 26910).", source=ds.source,
                           transformation="projected to EPSG 26910 where the source differs", used_by=ds.used)
                st = {"row_count": n}
            elif af.name.lower() in ("shape_length", "shape_area"):
                what = ("Line length or polygon perimeter" if af.name.lower() == "shape_length" else "Polygon area")
                row.update(description=f"{what}, calculated by the geodatabase.",
                           units="meters" if af.name.lower() == "shape_length" else "square meters",
                           source="geodatabase", transformation="computed by the geodatabase", used_by="")
                st = field_stats(df[af.name] if af.name in df.columns else None, n, "Double")
                st["top_values"] = None
            else:
                f = spec.get(af.name)
                if f is None:
                    raise SystemExit(f"{ds.name}.{af.name} is in the geodatabase but not in the spec")
                user += 1
                score = f.ftype == "DOUBLE" and f.name[:2] in ("E_", "S_", "V_")
                row.update(description=f.desc, units=f.units or ("score, 0 to 3" if score else ""), valid_values=f.values,
                           source=f.src or f"{ds.src_layer}.{f.name}", transformation=f.how or "copied unchanged",
                           used_by=f.used)
                st = field_stats(df[af.name] if af.name in df.columns else None, n, t)
            row.update(st)
            drows.append(row)
        absent = set(spec) - {af.name for af in afields}
        if absent:
            raise SystemExit(f"{ds.name}: spec fields missing from the geodatabase: {sorted(absent)}")
        sr = arcpy.Describe(path).spatialReference.name if ds.geom else None
        crows.append({"dataset": ds.name, "feature_dataset": ds.group, "dataset_type": "Feature class" if ds.geom else "Table",
                      "geometry_type": geom_word or None, "row_count": n, "field_count": user, "title": ds.title,
                      "description": ds.desc, "source": ds.source, "row_filter": ds.rows, "primary_key": ds.key,
                      "relates_to": ds.relates, "used_by": ds.used, "spatial_reference": sr, "built": built})
        log.info(f"{ds.name}: {n:,} rows, {user} fields described")
    return drows, crows


def meta_tables(drows: list, crows: list) -> tuple[Dataset, Dataset]:
    dd = Dataset("DataDictionary", "", "", "Field-level data dictionary",
                 "One row per field in every feature class and table, with its alias, type, units, description, valid "
                 "values, source, transformation, the pages and scripts that read it, and value statistics at build time.",
                 "scripts/build_curated_gdb.py", "DataDictionary", "All fields.", "dataset and field_name",
                 "DatasetCatalog.dataset", "Reference only; no page or script reads it.", DICT_FIELDS)
    cat = Dataset("DatasetCatalog", "", "", "Dataset catalog",
                  "One row per feature class and table, with what it holds, where it comes from, which rows are kept, its "
                  "key, its joins, and what reads it.", "scripts/build_curated_gdb.py", "DatasetCatalog", "All datasets.",
                  "dataset", "DataDictionary.dataset", "Reference only; no page or script reads it.", CATALOG_FIELDS)
    return dd, cat


def self_rows(ds: Dataset, n: int) -> list:
    """Dictionary rows for the two metadata tables themselves (no value statistics)."""
    out = [{"dataset": ds.name, "feature_dataset": "", "field_order": 1, "field_name": "OBJECTID", "alias": "OBJECTID",
            "field_type": "OID", "description": "Row ID assigned by the geodatabase.", "source": "geodatabase",
            "transformation": "assigned at build time", "row_count": n}]
    for i, f in enumerate(ds.fields, 2):
        out.append({"dataset": ds.name, "feature_dataset": "", "field_order": i, "field_name": f.name, "alias": f.alias,
                    "field_type": {"TEXT": "Text", "SHORT": "Short", "LONG": "Long", "DOUBLE": "Double", "DATE": "Date"}[f.ftype],
                    "field_length": f.length, "units": f.units, "description": f.desc, "valid_values": f.values,
                    "source": "scripts/build_curated_gdb.py", "transformation": "written at build time", "row_count": n})
    return out


# ----------------------------------------------------------------------------------------
# checks against the published files

def check(gdb: str, sets: list, cfg: dict, restricted: set, log) -> int:
    """Compare the curated layers with data/processed/results (written by publish_results.py from the same geodatabases).
    Returns the number of problems; differences in values are reported, not fatal (the analysis may be newer)."""
    import pyogrio
    res = REPO / cfg["paths"]["processed"] / "results"
    problems = 0

    def cmp(layer, key, csv, fields, key_int=False):
        nonlocal problems
        p = res / csv
        if not p.exists():
            log.info(f"check {layer}: {csv} not published; skipped")
            return
        pub = pd.read_csv(p) if csv.endswith(".csv") else pd.DataFrame(
            [f["properties"] for f in json.loads(p.read_text(encoding="utf-8"))["features"]])
        cur = pyogrio.read_dataframe(gdb, layer=layer, read_geometry=False, columns=[key] + fields)
        if key_int:
            pub[key] = pd.to_numeric(pub[key], errors="coerce").astype("Int64")
            cur[key] = cur[key].astype("Int64")
        m = cur.merge(pub[[key] + [f for f in fields if f in pub.columns]], on=key, how="outer", suffixes=("", "_pub"),
                      indicator=True)
        only = m["_merge"].value_counts().to_dict()
        msg = [f"rows curated {len(cur):,}, published {len(pub):,}, both {only.get('both', 0):,}"]
        if only.get("left_only") or only.get("right_only"):
            problems += 1
        both = m[m["_merge"] == "both"]
        for f in fields:
            if f + "_pub" not in both.columns:
                continue
            a, b = both[f], both[f + "_pub"]
            if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                diff = ~(((a - b).abs() <= 0.006) | (a.isna() & b.isna()))
            else:
                diff = a.fillna("").astype(str) != b.fillna("").astype(str)
            if diff.any():
                msg.append(f"{f} differs on {int(diff.sum())}")
        log.info(f"check {layer} vs {csv}: " + "; ".join(msg))

    if restricted:
        cmp("Culverts", "culvert_id", "culverts_results.csv", ["V_max", "V_class", "E_FLC_hist", "load_ratio_100", "d_eq_in"])
    cmp("Bridges", "bridge_id", "bridges_results.geojson", ["V_max", "V_class", "E_FLB_hist"])
    cmp("Roads", "src_objectid", "roads_vulnerability.csv", ["V_max", "V_class", "C_class", "criticality_pctl"], key_int=True)
    cmp("ActiveTransportation", "at_id", "paths_wildfire.geojson", ["V_max", "V_class", "E_WFAT_hist"], key_int=True)
    cmp("TransitHubs", "tc_id", "transit_wildfire.geojson", ["V_max", "V_class", "E_WFTC_hist"], key_int=True)
    if restricted:
        for layer, col in (("Culverts", "jurisdiction"), ("CulvertCondition", "jurisdiction")):
            v = pyogrio.read_dataframe(gdb, layer=layer, read_geometry=False, columns=[col, "culvert_id"])
            bad = int(v[col].isin(restricted).sum() + v["culvert_id"].astype(str).str.startswith(tuple(restricted)).sum())
            if bad:
                problems += 1
                log.error(f"{layer}: {bad} restricted rows present")
            else:
                log.info(f"check {layer}: no restricted rows")
    return problems


# ----------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overwrite", action="store_true", help="delete and rebuild the curated geodatabase")
    ap.add_argument("--include-restricted", action="store_true",
                    help="keep the NDOT rows; writes curated.restricted_gdb on TRPA storage")
    ap.add_argument("--resume", action="store_true",
                    help="keep the datasets an interrupted run already wrote and build the rest")
    args = ap.parse_args()
    log = get_logger("build_curated_gdb")
    cfg = load_cfg()
    import arcpy

    cu = cfg["curated"]
    out = Path(cu["restricted_gdb"] if args.include_restricted else cu["gdb"])
    if args.include_restricted and REPO in out.resolve().parents:
        raise SystemExit(f"{out} is under the repo; a restricted build stays on TRPA storage")
    from culvert_profile import restricted_jurisdictions
    restricted = set() if args.include_restricted else (restricted_jurisdictions(cfg) | {"NDOT"})
    gdb = str(out)
    if arcpy.Exists(gdb) and not args.resume:
        if not args.overwrite:
            raise SystemExit(f"{gdb} exists. Re-run with --overwrite to rebuild it, or --resume to finish it.")
        log.warning(f"Deleting {gdb}")
        arcpy.management.Delete(gdb)
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(str(out.parent), out.name)
    sr = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))
    sets = datasets(cfg, bool(args.include_restricted))
    for group in dict.fromkeys(ds.group for ds in sets if ds.group):
        if not arcpy.Exists(f"{gdb}\\{group}"):
            arcpy.management.CreateFeatureDataset(gdb, group, sr)
    log.info(f"{'Resuming' if args.resume else 'Building'} {gdb} "
             f"({'restricted, every jurisdiction' if args.include_restricted else 'public jurisdictions'})")

    ctx = {"restricted": restricted, "out_gdb": gdb}
    for ds in sets:
        if args.resume and arcpy.Exists(_path(gdb, ds)):
            log.info(f"{ds.name}: already written; kept")
            continue
        data = BUILDERS.get(ds.name, build_surface)(ds, cfg, ctx, log)
        write_rows(gdb, ds, data, sr, log)
    if args.resume:
        sync_aliases(gdb, sets, log)

    a = {ds.name: _path(gdb, ds) for ds in sets}
    relate(gdb, "Culvert_has_Condition", a["Culverts"], a["CulvertCondition"], "culvert_id", "culvert_id",
           "Inspections", "Culvert", log)
    relate(gdb, "Road_has_Culverts", a["Roads"], a["Culverts"], "src_objectid", "parent_segment_id", "Culverts", "Road", log)
    relate(gdb, "Road_has_Bridges", a["Roads"], a["Bridges"], "src_objectid", "parent_segment_id", "Bridges", "Road", log)
    relate(gdb, "Watershed_has_Culverts", a["CulvertWatersheds"], a["Culverts"], "crossing_id", "crossing_id",
           "Culverts", "Drainage area", log)
    for name, flds, unique in (("Roads", ["src_objectid"], True), ("Culverts", ["culvert_id"], True),
                               ("Culverts", ["crossing_id"], False), ("Culverts", ["parent_segment_id"], False),
                               ("CulvertCondition", ["culvert_id"], False), ("CulvertWatersheds", ["crossing_id"], True),
                               ("Bridges", ["bridge_id"], True), ("Bridges", ["parent_segment_id"], False),
                               ("ActiveTransportation", ["at_id"], True), ("TransitHubs", ["tc_id"], True)):
        idx = f"{name[:12]}_{flds[0][:16]}_idx"
        if idx in {i.name for i in arcpy.ListIndexes(a[name])}:
            continue
        try:
            arcpy.management.AddIndex(a[name], flds, idx, "UNIQUE" if unique else "NON_UNIQUE")
        except Exception as e:  # noqa: BLE001
            log.warning(f"{name}.{flds[0]}: index not added ({e})")
    for ds in sets:
        try:
            set_metadata(a[ds.name], ds, bool(args.include_restricted))
        except Exception as e:  # noqa: BLE001
            log.warning(f"{ds.name}: metadata not written ({e})")

    drows, crows = dictionary_rows(gdb, sets, log)
    dd, cat = meta_tables(drows, crows)
    drows += self_rows(dd, len(drows) + len(dd.fields) + 1 + len(cat.fields) + 1) + self_rows(cat, len(crows) + 2)
    for t in (dd, cat):
        crows.append({"dataset": t.name, "feature_dataset": "", "dataset_type": "Table", "row_count": None,
                      "field_count": len(t.fields), "title": t.title, "description": t.desc, "source": t.source,
                      "row_filter": t.rows, "primary_key": t.key, "relates_to": t.relates, "used_by": t.used,
                      "built": pd.Timestamp.today().normalize()})
    ddf = pd.DataFrame(drows).reindex(columns=[f.name for f in DICT_FIELDS])
    ddf.loc[ddf["dataset"] == "DataDictionary", "row_count"] = len(ddf)
    cdf = pd.DataFrame(crows).reindex(columns=[f.name for f in CATALOG_FIELDS])
    cdf.loc[cdf["dataset"] == "DataDictionary", "row_count"] = len(ddf)
    cdf.loc[cdf["dataset"] == "DatasetCatalog", "row_count"] = len(cdf)
    for t in (dd, cat):
        if arcpy.Exists(_path(gdb, t)):
            arcpy.management.Delete(_path(gdb, t))
    write_rows(gdb, dd, ddf, sr, log)
    write_rows(gdb, cat, cdf, sr, log)
    for t in (dd, cat):
        set_metadata(_path(gdb, t), t, bool(args.include_restricted))
    for t, df in ((dd, ddf), (cat, cdf)):
        p = out.parent / f"{out.stem}_{t.name}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        log.info(f"{t.name}: {len(df):,} rows -> {p}")

    problems = check(gdb, sets, cfg, restricted, log)
    log.info(f"Done: {len(sets)} datasets, {len(ddf):,} dictionary rows, {problems} check problem(s)")


if __name__ == "__main__":
    main()
