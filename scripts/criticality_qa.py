"""Criticality QA: outlier checks on the published criticality table, for html/criticality-qa.html.

Reads data/processed/results/roads_criticality.json (Streets_Network_Clean.ipynb section 13) and
roads_geometry.geojson (publish_results.py), runs the checks below, and writes
data/processed/results/criticality_qa.json. Re-run after every criticality rebuild:

    python scripts/criticality_qa.py

Checks marked "open" are outliers nobody has fixed; "by design" ones follow from the method (relative
quarters, equity weight); "fixed" ones were corrected on Oct. 30, 2026 and are listed for review.
Topology comes from the geometry: two segments touch when they share an endpoint (rounded to 1e-5 deg).
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RES = REPO / "data" / "processed" / "results"
CRIT, GEOM, OUT = RES / "roads_criticality.json", RES / "roads_geometry.geojson", RES / "criticality_qa.json"

MAJOR = {"trunk", "primary", "secondary", "tertiary"}
CORRIDOR = {"trunk", "primary", "secondary"}
MINOR = {"residential", "service", "unclassified", "unknown", "living_street"}
EQ = ["Below_Poverty_Household_max", "Speak_English_Not_Well_Not_at_A_max",
      "Vehicle_Available_0_max", "With_Disability_max"]
STUB_M = 16          # a stub: shorter than the AADT join's minimum overlap reaches (15 m / 90 percent)

CATS = {  # key: (status, label, what, next step)
    "traffic_stub": ("open", "Stub still takes highway traffic",
        "A stub of 16 m or less touching a major road, with the same traffic class (3 or higher) as that road. "
        "It still passes the AADT join, usually because it runs nearly along the highway (a slip lane or turn pocket).",
        "Check the segment against imagery; if it is a driveway or pocket, set its traffic class to 1 or tighten the join."),
    "stub_access": ("open", "Stub carries highway-level access",
        "A minor stub of 12.5 m or less touching a major road, with an access class of 3 or higher and more than twice "
        "the residents routed over any minor street it touches. The OD join "
        "(export_protect_va.py) tests short streets the same way the detour join did before the Oct. 30 fix, "
        "so some of these may hold the highway's routed residents.",
        "Apply the export_slr.py midpoint test to export_protect_va.build_update and re-export OD (no re-route needed)."),
    "major_low_traffic": ("open", "Major road at the lowest traffic class",
        "A trunk, primary, or secondary segment matched to a StreetLight value low enough for traffic class 1.",
        "Check the matched StreetLight zone (aadt_zone_name); the match may be a parallel local street."),
    "spike": ("open", "Top quarter, every neighbor below the median",
        "A top-quarter segment whose every touching segment sits below the 50th percentile. Criticality should "
        "change gradually along a route, so a lone bright block often means a gap or bad link in the network.",
        "Look at the detour around it: a missing connection nearby can inflate one block's detour."),
    "shape_doubles_back": ("open", "Line doubles back on itself",
        "The segment's line turns back more than 150 degrees between two legs of 10 m or more, usually retracing a "
        "neighbor: most of these lie partly on top of other segments. The road does not do this; the line was built "
        "wrong in Streets_Network_Tahoe. The length is overstated, the map draws a spike, and joins that test "
        "overlap can miss (Mount Rose Highway 3744 scored zero traffic until Oct. 30).",
        "Rebuild these lines from the Overture segment geometry (segment_id) in the base network, then rerun the build."),
    "parallel_split": ("open", "Parallel pair scored far apart",
        "Two segments sharing both endpoints (a frontage road, loop, or split carriageway) whose percentiles differ "
        "by more than 25 points. Usually expected: the highway carries the traffic and the loop does not.",
        "Spot-check; mostly informational."),
    "unnamed_major": ("open", "Major road with no name",
        "A trunk, primary, secondary, or tertiary segment with no street name in Overture. The score is fine; "
        "the label is missing on the map and in exports.",
        "Fill the name from the touching segments of the same class."),
    "unknown_top": ("open", "Unknown road class in the top quarter",
        "A segment Overture leaves unclassified ('unknown') that ranks in the top quarter.",
        "Confirm the road type."),
    "no_geometry": ("open", "Scored but missing from the map",
        "In roads_criticality.json but not in roads_geometry.geojson, so the segment is scored but never drawn.",
        "Check publish_results.py's street read for the dropped rows."),
    "low_use_capped": ("fixed", "Detour capped: road almost nobody uses",
        "A minor road with a long detour but traffic class 1 and fewer than 10 residents routed. Its detour class "
        "was capped at 1 on Oct. 30 (detour_low_use). Mostly forest and seasonal roads.",
        "Confirm on the ground: some may be fire or evacuation access that the routing does not model."),
    "equity_only_top": ("by design", "Top quarter from equity alone",
        "Traffic, detour, and access are all at the lowest class; the neighborhood equity counts alone lift the "
        "segment past the top-quarter cut.",
        "A weighting decision, not an error: see the note on relative quarters."),
    "one_step_top": ("by design", "Top quarter from one step on one input",
        "A minor street whose traffic, detour, and access classes sum to 4: one input is one class above the "
        "lowest. With 70 percent of segments at the floor, that is enough to reach the top quarter.",
        "A classification decision, not an error: see the note on relative quarters."),
}


def reversal(coords, min_leg_m=10):
    """Largest turn (degrees) between two consecutive legs that are both at least min_leg_m long.

    Lon/lat are scaled to meters at the basin's latitude, close enough for a 10 m threshold."""
    c = np.asarray(coords, dtype=float)
    if len(c) < 3:
        return 0.0
    xy = np.c_[c[:, 0] * 111320 * np.cos(np.radians(39.1)), c[:, 1] * 110540]
    v = np.diff(xy, axis=0)
    leg = np.hypot(v[:, 0], v[:, 1])
    turn = np.degrees(np.abs((np.diff(np.arctan2(v[:, 1], v[:, 0])) + np.pi) % (2 * np.pi) - np.pi))
    ok = (leg[:-1] >= min_leg_m) & (leg[1:] >= min_leg_m)
    return float(turn[ok].max()) if ok.any() else 0.0


def load():
    d = json.loads(CRIT.read_text(encoding="utf-8"))
    df = pd.DataFrame(d["rows"], columns=d["columns"]).set_index("src_objectid")
    g = json.loads(GEOM.read_text(encoding="utf-8"))
    props, ends = {}, {}
    k = lambda p: (round(p[0], 5), round(p[1], 5))
    for f in g["features"]:
        p, c = f["properties"], f["geometry"]["coordinates"]
        props[p["src_objectid"]] = dict(p, max_reversal=reversal(c))
        ends[p["src_objectid"]] = (k(c[0]), k(c[-1]))
    meta = pd.DataFrame.from_dict(props, orient="index")[["name", "class", "seg_len_m", "max_reversal"]]
    df = df.join(meta, how="left")
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    return d["meta"], df, ends


def checks(df, ends):
    node = defaultdict(set)
    for s, (a, b) in ends.items():
        node[a].add(s)
        node[b].add(s)
    nb = {s: (node[a] | node[b]) - {s} for s, (a, b) in ends.items()}
    pc, cls = df["criticality_pctl"].to_dict(), df["class"].to_dict()
    df["q"] = pd.cut(df.criticality_pctl, [-1, 25, 50, 75, 101], right=False, labels=[0, 1, 2, 3]).astype(int)
    df["nb_max_pctl"] = [max((pc[t] for t in nb.get(s, ()) if t in pc), default=np.nan) for s in df.index]
    df["touches_major"] = [any(cls.get(t) in MAJOR for t in nb.get(s, ())) for s in df.index]
    eqz = sum((df[f] - df[f].mean()) / df[f].std(ddof=0) for f in EQ) / 4
    df["equity_part"] = (df.get("meta_w_equity", 0.1) * eqz).round(3)
    minor, top, ln = df["class"].isin(MINOR), df.q == 3, df.seg_len_m

    F = {}
    aadt = df.AADT_Jenks_Score.to_dict()
    F["traffic_stub"] = [s for s in df.index[minor & (ln <= STUB_M) & (df.AADT_Jenks_Score >= 3)]
                         if any(cls.get(t) in MAJOR and aadt.get(t) == aadt[s] for t in nb.get(s, ()))]
    # a street's mouth carries everyone on the street, so only flag a stub that carries well over what
    # the minor streets it touches carry: more than twice their maximum
    od = df.OD_Traffic_Avg.to_dict()
    df["nb_minor_od"] = [max((od[t] for t in nb.get(s, ()) if cls.get(t) in MINOR and t in od), default=0.0)
                         for s in df.index]
    F["stub_access"] = df.index[minor & (ln <= 12.5) & (df.OD_Traffic_Jenks_Score >= 3) & df.touches_major
                                & (df.OD_Traffic_Avg > 2 * df.nb_minor_od)].tolist()
    F["major_low_traffic"] = df.index[df["class"].isin(CORRIDOR) & (df.AADT_Jenks_Score == 1)].tolist()
    F["spike"] = df.index[top & (df.nb_max_pctl < 50)].tolist()
    F["shape_doubles_back"] = df.index[df.max_reversal > 150].tolist()
    pairs = defaultdict(list)
    for s, (a, b) in ends.items():
        pairs[tuple(sorted([a, b]))].append(s)
    F["parallel_split"] = sorted({s for v in pairs.values() if len(v) > 1
                                  and max(pc.get(x, 0) for x in v) - min(pc.get(x, 0) for x in v) > 25
                                  for s in v if s in pc})
    F["unnamed_major"] = df.index[df["class"].isin(MAJOR) & (df["name"] == "")].tolist()
    F["unknown_top"] = df.index[top & (df["class"] == "unknown")].tolist()
    F["no_geometry"] = df.index[df["class"].isna()].tolist()
    F["low_use_capped"] = df.index[df.get("detour_low_use", pd.Series(0, index=df.index)) == 1].tolist()
    low3 = (df.AADT_Jenks_Score == 1) & (df.SLR_Diff_Length_Jenks_Score == 1) & (df.OD_Traffic_Jenks_Score == 1)
    F["equity_only_top"] = df.index[top & low3].tolist()
    F["one_step_top"] = df.index[top & minor & ((df.AADT_Jenks_Score + df.SLR_Diff_Length_Jenks_Score
                                                 + df.OD_Traffic_Jenks_Score) == 4)].tolist()
    return F


def main():
    meta, df, ends = load()
    df["meta_w_equity"] = meta["weights"]["equity"]
    F = checks(df, ends)
    order = list(CATS)
    flags = defaultdict(list)
    for k in order:
        for s in F[k]:
            flags[s].append(k)
    raw = "SLR_Diff_Length_Jenks_Raw" if "SLR_Diff_Length_Jenks_Raw" in df else "SLR_Diff_Length_Jenks_Score"
    rows = []
    for s, ks in flags.items():
        r = df.loc[s]
        num = lambda v, d=None: None if pd.isna(v) else (round(float(v), d) if d is not None else int(v))
        rows.append({"id": s, "name": r["name"] or None, "class": None if pd.isna(r["class"]) else r["class"],
                     "len": num(r.seg_len_m, 1), "flags": ks, "status": CATS[ks[0]][0],
                     "q": int(r.q), "pctl": num(r.criticality_pctl, 2),
                     "aadt": num(r.AADT_Jenks_Score), "detour": num(r.SLR_Diff_Length_Jenks_Score),
                     "detour_raw": num(r[raw]), "detour_m": num(r.slr_diff_length_max, 0),
                     "access": num(r.OD_Traffic_Jenks_Score), "residents": num(r.OD_Traffic_Avg, 1),
                     "equity": num(r.equity_part, 3), "nb_max": num(r.nb_max_pctl, 2),
                     "nb_minor_res": num(r.nb_minor_od, 1)})
    top = df[df.q == 3]
    summary = {
        "segments": len(df), "top_quarter": int(len(top)),
        "top_cut_score": round(float(top.criticality_score.min()), 4),
        "at_floor": int(((df.AADT_Jenks_Score == 1) & (df.SLR_Diff_Length_Jenks_Score == 1)
                         & (df.OD_Traffic_Jenks_Score == 1)).sum()),
        "top_by_class": {k: int(v) for k, v in top["class"].value_counts().items()},
    }
    cats = {k: {"status": v[0], "label": v[1], "what": v[2], "next": v[3], "count": len(F[k])}
            for k, v in CATS.items()}
    out = {"meta": {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": meta.get("generated"),
                    "weights": meta["weights"]},
           "summary": summary, "categories": cats, "rows": rows}
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {len(rows):,} flagged segments")
    for k, c in cats.items():
        print(f"  {c['status']:<9} {k:<18} {c['count']:>5}")


if __name__ == "__main__":
    main()
