"""Cross-check the culvert capacity side of FL-C against the CULVERT tool's method.

    python scripts/culvert_crosscheck.py              # summary to the log, per-crossing CSV to outputs/
    python scripts/culvert_crosscheck.py --rp 25      # compare at the 25-year flow instead of the headline

CULVERT (Climate and Upland Loading Vulnerability Evaluation and Risk Analysis Tool,
https://culvert-at-risk.org; USDA Forest Service Southern Research Station, University of North
Georgia, University of Idaho; FHWA funded) screens crossings by comparing peak flow with a
capacity from FHWA HDS-5. Its backend utilities are public (MIT) at
https://github.com/SouravDSGit/Culvert_utility; the capacity rule below is ported from
utils/subroutine_culvert_discharge_capacity.py as written (commit of Jan. 22, 2026), defaults
included, so the comparison is the tool's method and not a corrected one. Differences from
culvert_profile.py, by design of the two tools:

  - headwater: CULVERT defaults to HW = 1.5 D; the profile uses HW/D = profile.hw_d (1.0)
  - inlet coefficients: CULVERT uses c = 0.038, Y = 0.6 for every shape and inlet; the profile
    uses the HDS-5 table row for the culvert's material, shape, and inlet (profile.inlet_control)
  - outlet control: CULVERT offers it (L = 30 m, S = 1 percent, TW = 0.5 D, Ke = 0.5, Manning n
    by material, concrete when unknown); the profile has none. HDS-5 takes the lower of inlet and
    outlet capacity; CULVERT makes the user pick one, so both and their minimum are reported
  - in CULVERT's HW/D <= 1.2 branch the slope term has the opposite sign to HDS-5; at its 1.5 D
    default that branch is never reached, so it does not affect these numbers

The peak flow is held fixed (the published q_event columns), so every difference is capacity.
Reads data/processed/results/culverts_results.csv (public rows only; restricted records are
never in it). Crossings flagged size_suspect are left out, as in the published loading ratio.
Writes outputs/culvert_crosscheck.csv (gitignored). Circular equivalent diameter (d_eq_in) for
every barrel, since shape is not in the published file.
"""

from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

from score_vulnerability import loading_ratio_score
from va_common import REPO, get_logger, load_cfg

G = 32.2  # ft/s2
FLC_S2_WEIGHT = 0.30  # FL-C S2 weight in score_vulnerability.py (V = 0.30 E + 0.25 S1 + 0.30 S2 + 0.15 S3)

# CULVERT defaults (subroutine_culvert_discharge_capacity.py): facts about the external tool,
# not parameters of this assessment, so they stay here rather than in config.yaml.
CULVERT_HW_D = 1.5
CULVERT_TW_D = 0.5
CULVERT_C, CULVERT_Y = 0.038, 0.6
CULVERT_L_FT = 30.0 / 0.3048
CULVERT_SLOPE = 0.01
CULVERT_KE = 0.5
CULVERT_N = {"concrete": 0.012, "plastic": 0.009, "corrodible_metal": 0.024, "unknown": 0.012}


def culvert_inlet(d_ft: pd.Series) -> pd.Series:
    """CULVERT inlet control per barrel (cfs), circular: its HW/D > 1.2 branch at HW = 1.5 D."""
    area = math.pi * d_ft ** 2 / 4.0
    return area * np.sqrt(d_ft) * math.sqrt((CULVERT_HW_D - CULVERT_Y) / CULVERT_C)


def culvert_outlet(d_ft: pd.Series, n: pd.Series) -> pd.Series:
    """CULVERT outlet control per barrel (cfs), circular, full barrel, h_o = max(TW, D)."""
    area = math.pi * d_ft ** 2 / 4.0
    r = d_ft / 4.0
    head = CULVERT_HW_D * d_ft - np.maximum(CULVERT_TW_D * d_ft, d_ft) + CULVERT_SLOPE * CULVERT_L_FT
    loss = 1.0 + CULVERT_KE + 29.2 * n ** 2 * CULVERT_L_FT / r ** (4.0 / 3.0)
    return area * np.sqrt((2.0 * G * head.clip(lower=0)) / loss)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rp", type=int, help="return period to compare (default profile.headline_rp)")
    args = ap.parse_args()
    log = get_logger("culvert_crosscheck")
    cfg = load_cfg()
    p = cfg["profile"]
    rp = args.rp or p["headline_rp"]
    q_col = f"q_event_{rp}_cfs"

    src = REPO / "data" / "processed" / "results" / "culverts_results.csv"
    cul = pd.read_csv(src, low_memory=False)
    log.info(f"{len(cul)} published culverts from {src.relative_to(REPO)}")

    d_ft = cul["d_eq_in"] / 12.0
    n = cul["material_class"].map(CULVERT_N).fillna(CULVERT_N["unknown"])
    cul["cv_inlet_cfs"] = culvert_inlet(d_ft)
    cul["cv_outlet_cfs"] = culvert_outlet(d_ft, n)

    # one row per crossing: capacities summed over barrels, flow and our capacity carried
    key = cul["crossing_id"].fillna(cul["culvert_id"])
    x = cul.groupby(key).agg(
        jurisdiction=("jurisdiction", "first"), road_name=("road_name", "first"),
        barrels=("culvert_id", "size"), d_eq_in=("d_eq_in", "max"),
        contrib_area_ac=("contrib_area_ac", "first"), q_method=("q_method", "first"),
        q_event=(q_col, "first"), q_cap_profile=("q_cap_crossing_cfs", "first"),
        cv_inlet=("cv_inlet_cfs", lambda s: s.sum(min_count=1)),
        cv_outlet=("cv_outlet_cfs", lambda s: s.sum(min_count=1)),
        size_suspect=("size_suspect", "max"),
    )
    x.index.name = "crossing_id"
    x["cv_control"] = x[["cv_inlet", "cv_outlet"]].min(axis=1, skipna=False)
    x["cv_controls"] = np.where(x["cv_outlet"] < x["cv_inlet"], "outlet", "inlet")

    ok = x["q_event"].notna() & x["q_cap_profile"].notna() & x["cv_inlet"].notna() & (x["size_suspect"] != 1)
    log.info(f"{len(x)} crossings; {int(ok.sum())} comparable ({int((x['size_suspect'] == 1).sum())} size_suspect "
             f"left out, {int((~ok & (x['size_suspect'] != 1)).sum())} with no recorded size or no flow)")
    x = x[ok].copy()

    for tag, cap in (("profile", "q_cap_profile"), ("cv_inlet", "cv_inlet"),
                     ("cv_outlet", "cv_outlet"), ("cv_control", "cv_control")):
        x[f"ratio_{tag}"] = (x["q_event"] / x[cap]).round(2)
        x[f"s2_{tag}"] = x[f"ratio_{tag}"].map(loading_ratio_score)
        x[f"fails_{tag}"] = (x[f"ratio_{tag}"] > 1.0).astype(int)

    log.info(f"Q{rp} exceeds capacity (CULVERT's Vulnerable flag, Qc < Qp), {len(x)} crossings:")
    for tag, label in (("profile", f"profile, HDS-5 table inlet at HW/D {p['hw_d']:g}"),
                       ("cv_inlet", f"CULVERT inlet control, HW/D {CULVERT_HW_D:g}"),
                       ("cv_outlet", "CULVERT outlet control, its defaults"),
                       ("cv_control", "CULVERT, lower of inlet and outlet")):
        f = int(x[f"fails_{tag}"].sum())
        log.info(f"  {label:<48} {f:>5}  ({100 * f / len(x):.1f} percent)")

    cap_ratio = (x["cv_inlet"] / x["q_cap_profile"]).replace([np.inf, -np.inf], np.nan)
    log.info(f"CULVERT inlet capacity / profile capacity: median {cap_ratio.median():.2f}, "
             f"10th to 90th percentile {cap_ratio.quantile(0.1):.2f} to {cap_ratio.quantile(0.9):.2f}")
    log.info(f"Outlet control governs CULVERT's capacity at {int((x['cv_controls'] == 'outlet').sum())} crossings")

    both = pd.crosstab(x["fails_profile"].map({0: "profile passes", 1: "profile fails"}),
                       x["fails_cv_control"].map({0: "CULVERT passes", 1: "CULVERT fails"}))
    log.info("Pass and fail agreement, profile against CULVERT lower of inlet and outlet:\n" + both.to_string())
    moved = pd.crosstab(x["s2_profile"].rename("profile S2"), x["s2_cv_control"].rename("CULVERT S2"))
    log.info("FL-C S2 loading-ratio score (draft half-point bands), profile rows against CULVERT columns:\n"
             + moved.to_string())
    dv = FLC_S2_WEIGHT * (x["s2_cv_control"] - x["s2_profile"])
    log.info(f"Swapping in CULVERT's capacity would move V_FLC by {dv.mean():+.2f} on average "
             f"(S2 weight {FLC_S2_WEIGHT:g}); {int((dv != 0).sum())} crossings change, "
             f"the largest drop {dv.min():+.2f}")

    out = REPO / "outputs" / "culvert_crosscheck.csv"
    out.parent.mkdir(exist_ok=True)
    cols = ["jurisdiction", "road_name", "barrels", "d_eq_in", "contrib_area_ac", "q_method", "q_event",
            "q_cap_profile", "cv_inlet", "cv_outlet", "cv_control", "cv_controls"] + \
           [c for c in x.columns if c.startswith(("ratio_", "s2_", "fails_"))]
    x[cols].round({"cv_inlet": 1, "cv_outlet": 1, "cv_control": 1}).rename(columns={"q_event": q_col}).to_csv(out)
    log.info(f"Wrote {out.relative_to(REPO)} ({len(x)} crossings)")


if __name__ == "__main__":
    main()
