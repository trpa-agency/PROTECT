# PROTECT: Hazard x Asset Pairs & Risk Index (v0.4)

**Task 3.3 Interactive Risk Index Mapping Tool** (PROTECT Plan, Task 3 Resilience Improvement Plan)

Plain-text source-of-record for the hazard-asset pairs and modeling approach. The interactive
version (with the data and model inventory and full framework) is the
[reference hub](html/reference-hub.html); this file and the hub's pairs grid are kept in mirror.

The risk index follows the **FHWA VAST framework**. Four sub-indices (Exposure, Sensitivity, Asset
Value, and Adaptive Capacity, reverse-scored) combine into a **Master PROTECT Index**, weighted
alongside Criticality. Per ICF guidance, Sensitivity is weighted lightly (about 10-20 percent) and
Criticality substantially (about 30 percent, just below Exposure).

Sources: 5/20/2026 ICF/TRPA VA deck (sensitivity & criticality approach), the partner pairing
review (summer 2026), `PROTECT_RiskIndexTool_Scoping_v0.1.docx`.

> v0.4 (Aug. 3, 2026) merges the partner pairing review with the v0.3 list: nine pairs added
> (avalanche-bridges, landslide-bridges, earthquake-roads, and the active transport / transit
> center / marina pairs), Flooding-Culverts and the two Debris Flow pairs restored (they were
> dropped by accident when the review's include column was flattened), and Landslide-Culverts
> (LS-C) folded into Debris Flow-Culverts (DF-C). v0.3 superseded v0.2 (Risk = Vulnerability x
> Criticality, 9 pairs) by adopting the FHWA VAST model.

---

## 1. Hazard x Asset pairs (canonical list: 6 advancing, 12 candidate, 2 screening)

Impact: **PC** = physical damage + cascading operational disruption; **OP** = operational only.
Status: **Advancing** (locked for geospatial scoring), **Candidate** (under review with partners),
**Screening** (operational-only; asset target still TBD).

| ID | Hazard | Asset | Impact | Status | Exposure inputs | Sensitivity indicators | Notes |
|----|--------|-------|--------|--------|-----------------|------------------------|-------|
| AV-R | Avalanche | Roads | OP | Advancing | SNODAS / Topofire SWE; OpenTopography LiDAR + RAMMS runout | Road elevation (no unique sensitivity) | Initial focus: Hwy 89, 207, 431; confirm scope with NDOT/Caltrans |
| FL-B | Flooding | Bridges | PC | Advancing | HEC-RAS bridge scour; USGS StreamStats; FEMA floodplains | Bridge condition, deck rating/type, scour criticality, elevation, channel & water-opening adequacy | Bridge condition data request open with Caltrans/NDOT |
| FL-C | Flooding | Culverts | PC | Advancing | USGS StreamStats (peak discharge); NOAA Atlas 14; FEMA floodplains; HEC-RAS scour | Culvert condition, scour, capacity, age, channel condition | TRPA culvert layer compiled (7,858 assets, 6 jurisdictions); CULVERT screening on the Storm Events page |
| FL-R | Flooding | Roads | PC | Advancing | FEMA floodplains; USGS StreamStats; HEC-RAS; road elevation vs. inundation | Pavement condition, foundation / permeable sub-base, elevation, age | Lowland and valley segments most exposed |
| LS-R | Landslide | Roads | PC | Advancing | USGS Landslide Susceptibility; CA Geological Survey; LiDAR + RAMMS runout | Pavement condition, road elevation | Runout extents via RAMMS or r.avaflow |
| WF-R | Wildfire | Roads | PC | Advancing | Wildfire Risk to Communities; CA Pyregence; fire-weather index (Cal-Adapt); commercial fire modeling | No unique sensitivity indicators | Fire-modeling procurement is the critical-path dependency |
| AV-B | Avalanche | Bridges | PC | Candidate | | | |
| DF-C | Debris Flow | Culverts | PC | Candidate | Post-fire debris flow (HEC-HMS); USGS Landslide Susceptibility; CA Geological Survey; CA Pyregence; precip (Cal-Adapt) | Culvert condition, capacity, scour | Split from landslide per 5/20; absorbs LS-C per Aug 2026 review; post-fire compounding required per ICF; WildCat modeling planned |
| DF-R | Debris Flow | Roads | PC | Candidate | Post-fire debris flow (HEC-HMS); LiDAR runout; precip | Pavement condition, road elevation | Split from landslide per 5/20; July 14 event hindcast on the Storm Events page |
| EQ-B | Earthquake | Bridges | PC | Candidate | USGS Seismic Hazard Maps; ComCat; ShakeMaps | Seismic retrofit status, bridge condition, age | Identify bridges needing seismic retrofit |
| EQ-R | Earthquake | Roads | PC | Candidate | | | |
| FL-AT | Flooding | Active Transport | PC | Candidate | | | |
| LS-B | Landslide | Bridges | PC | Candidate | | | |
| WF-AT | Wildfire | Active Transport | PC | Candidate | | | |
| WF-M | Wildfire | Marinas | PC | Candidate | | | |
| WF-TC | Wildfire | Transit Centers | PC | Candidate | | | |
| WS-AT | Winter Storm | Active Transport | OP | Candidate | | | |
| WS-TC | Winter Storm | Transit Centers | OP | Candidate | | | |
| WD-R | Wind | Roads | OP | Screening | gridMET wind (Climate Engine); ASCE 7; criticality-focused | Operational: tree blow-down, power-line breaks | Asset target TBD: Roads and/or Power & Telecom |
| WS-R | Winter Storm | Roads | OP | Screening | SNODAS SWE; Cal-Adapt snow projections; NRI Winter Storm; criticality-focused | Operational: extended closure, plow-depot overrun, ITS power loss | Asset target TBD: Roads / Power / ITS |

Retired: **LS-C** (Landslide-Culverts) folded into DF-C, Aug. 3, 2026 - culvert mass-movement risk
is carried by the debris-flow pair.

---

## 2. Vulnerability sub-indices (FHWA VAST)

- **Exposure**: where and how intensely a hazard hits. Commercial fire-pathway modeling, HEC-RAS / StreamStats
  (flood inundation & scour), RAMMS (avalanche / landslide / debris-flow runout), WEPP (post-fire soil
  erosion and sediment delivery), wind strike zones, seiche zones, seismic / dam inundation.
- **Sensitivity** (weighted ~10-20 percent): asset fragility. Bridge / culvert condition, pavement
  age, road elevation; stormwater / IDF capacity. The TRPA Equity Study (vulnerable populations) is
  applied as a Justice40 multiplier.
- **Asset Value**: what is at stake. Strategic community assets, emergency staging, freight tonnage,
  transit, active transport, cascading assets (power, telecom).
- **Adaptive Capacity** (reverse-scored: high capacity = low vulnerability): network redundancy /
  detour ratios, redundant power (HIFLD), transit hubs, airport ICS proximity.

## 3. Criticality indicators

- **Roads** (DCTC / MWCOG): AADT, proximity to strategic community assets, community priority zones
  (TRPA-developed), detour length, transit & bike facilities on the asset. Bridges and culverts on a
  segment inherit the road's score. Interactive scoring is live in
  [`html/criticality-index.html`](html/criticality-index.html) (18,253 segments, adjustable weights).
- **Active Transportation**: proximity to strategic assets and other modes, community priority zones,
  emergency-vehicle accommodation.
- **Bus Stops**: ridership, community priority zones, proximity to strategic assets, multi-modal
  connectivity (or inherit the road segment's score).

## 4. Composite index architecture

`A. Exposure` + `B. Sensitivity` + `C. Asset / Adaptive Capacity (reverse)` -> `D. Master PROTECT Index`
(the single composite map for the Task 3.3 interactive tool).

## 5. Disruption-risk tool: RA2CE selected

**RA2CE** (Deltares) is the selected disruption-risk engine (Aug 2026), running on the
Overture-derived street network; analysis work lives in `scripts/ra2ce`. **Volpe RDR** was evaluated
and not pursued (retained as a reference for Task 3.4 BCA framing).

## 6. Data inventory

33 data elements mapped to VAST components (including a planned **WEPP** erosion/sediment service),
plus the model/tool inventory and composite-index architecture, are catalogued in the
**Data and Model Inventory** tab of the [reference hub](html/reference-hub.html) (the source of
record) and `PROTECT_DataModel_Inventory.xlsx`. Not reproduced here to avoid divergence.

## 7. Open decisions

Headline items: which Candidate pairs advance to robust geospatial analysis (partner review),
exposure scoring rubric per hazard (normalization scheme with ICF), analysis grain (segment vs.
parcel), climate-data sourcing for commercial flood data (TRPA purchase vs. add to ICF contract),
data hand-off contract, hosting domain, and public visibility. Climate-specific decisions live on
the [climate data page](html/climate-data.html) Open Decisions tab.
