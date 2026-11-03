# Handoff: debris flow exposure revision (decision 33)

**Status (Nov. 3, 2026): executed.** The plan below ran on Nov. 2 and 3 and is kept as the
record of it. The section 5 review led to decisions 34 to 37 (debris flow breaks and gates,
the pairs in the combined class, landslide by area share, the class-setting highest hazard),
all recorded with their numbers in `docs/SCORING_RUBRICS.md` v0.10; sections 5 to 8 are
superseded by those notes. The section 7 note to ICF went out separately.

Written Nov. 2, 2026 for a Claude Code session on `trpa-agency/PROTECT`; revised the same day
after a check against `main` at 909d8ef (still the tip after a fetch on Nov. 2). Read `CLAUDE.md`.

**Branch.** The local checkout is `mtb-arc11`: five print-map commits not on `main` (the 17
workshop maps) and 14 commits behind it. The print-map step in section 4 needs those commits.
Merge `main` into `mtb-arc11` and work there, or land `mtb-arc11` on `main` first; do not branch
fresh from `main`. Line numbers below are at 909d8ef; if a merge shifts them, search for the
quoted text.

House rules apply to everything below: no em-dashes, no staff names in committed files,
"percent" spelled out, Oxford commas, the HTML mirrors updated with the markdown. Do not commit
xlsx files.

## 1. What changes and why

Debris flow (DF-R, DF-B, DF-C) is scored today as option 1 with a stand-in: E1 mean upslope
slope 0.20, E2 contributing area 0.20, E3 TRPA most-likely fire severity 0.30 standing in for
predicted soil burn severity. Culverts read E1 and E2 from their own profile and E3 as the
watershed maximum; roads and bridges read E1 and E3 as maxima and E2 at the largest contributing
area they touch. The pairs are held out of the combined class
(`scoring.v_max_exclude: [DFC, DFB, DFR]`).

E2 scores 3 on anything under 0.25 square miles: 4,798 of 5,096 culverts at 909d8ef. As a
score it was a constant.

**What dropping E2 does on its own.** Rescoring the published culvert results at 909d8ef with
E2 dropped and today's maximum E3 kept gives a ceiling for the change (the share rule below can
only lower E3):

| DF-C class | 909d8ef | E2 dropped, maximum E3 (ceiling) | Same, with the 3 square mile gate |
|---|---|---|---|
| High | 2,745 | 2,268 | 2,239 |
| Medium | 2,347 | 2,788 | 2,788 |
| Low | 4 | 40 | 69 |

LS-C has 1,768 culverts High and FL-C 456. Dropping E2 moves DF-C High from 54 to at most 45
percent, and the gate reaches 29 culverts. The class shares are decided by the share rule on E3
(today 2,278 culverts sit at E3 = 3), not by dropping E2. Expect the section 6 fallback.

TRPA decision (Nov. 2, 2026): score debris flow the way wildfire is scored, from data in hand,
with the contracted package replacing the stand-in in December on the same breaks.

- Drop E2 as a weighted term. The USGS post-fire models treat basin area as a domain limit,
  not a likelihood predictor.
- Keep area as a gate on culverts and bridges: a contributing area over 3 square miles sets
  exposure to 0 (about the 8 square kilometer limit of USGS emergency assessments). The pair
  then reads 0.30 times sensitivity, which is Low; vulnerability itself is not zeroed, the same
  as any asset with exposure 0. A big river delivers a sediment-laden flood, which FL-B and FL-C
  already carry. Roads are not gated (see the large-river check in section 5).
- E1 is unchanged in source and sampling: culverts from their profile (`basin_slope_pct`), roads
  the highest class touching the segment, bridges the highest class within 25 m.
- E3 severity is the highest class covering at least 25 percent of the sampling area (the
  wildfire rule, decision 27), in place of the maximum. Culverts sample their contributing
  watershed, with the 25 m buffer where no watershed exists. Roads and bridges sample a 300 ft
  buffer, like wildfire. Bridge watersheds are December work. Not a majority: a basin that is 45
  percent High severity must read High.
- Exposure weights are the draft's proportions with E2 removed: 0.40 slope, 0.60 severity.
  Exposure keeps its 0.70 share of vulnerability on culverts and bridges (`scoring.dfc` and
  `scoring.dfb` weights unchanged); roads are V = E (decision 25).
- Sensitivity is untouched: DF-C opening size and condition (decision 7), DF-B the LS-B set,
  DF-R exposure only (decision 25).
- Class breaks stay the shared ones (Low under 1.0, Medium 1.0 to under 2.0, High 2.0 and
  over) until the distribution says otherwise. With E = 0.40 E1 + 0.60 E3 inside the severity
  layer:

  | Severity (E3) | E range | Medium from | High from |
  |---|---|---|---|
  | Low (1) | 0.6 to 1.8 | slope over 10 percent | never |
  | Moderate (2) | 1.2 to 2.4 | always | slope over 20 percent |
  | High (3) | 1.8 to 3.0 | always | slope over 5 percent |

  That is E, which is V on roads; culverts and bridges add 0.30 times sensitivity. Wildfire
  needed its own breaks (decision 26); debris flow may too. Decide on the numbers after the run.
- `v_max_exclude` is not changed until the review in section 5 is done. Putting the pairs
  back into `V_max` is the goal, gated on the class shares looking sane next to flooding and
  landslide.

**Open before the run: what "covering 25 percent" means.** `share_class()` takes the highest
class whose own share reaches 25 percent. A basin 30 percent outside the severity layer and 24,
23, and 23 percent Low, Moderate, and High reads E3 = 0, though 46 percent of it is Moderate or
worse. Watersheds mix classes more than 300 ft buffers do. The alternative, the highest class k
where class k or worse covers 25 percent, still stops single cells from setting the score.
Default: the per-class rule, as decision 27 is written. Build the sampler with a switch
(`e3_share_cumulative`, section 3) and report E3 both ways in section 5 so the choice is made on
numbers.

Decision 33 supersedes decision 16 (drainage-area breaks adopted) and amends decision 15
(option 1 stays the structure; option 2 Wildcat is still compared in December). The Oct. 26
consultant concurrence was on option 1 with E2; ICF gets a note (section 7).

## 2. Method text for the rubrics

Paste into `docs/SCORING_RUBRICS.md` section 4.4 as decision 33 and mirror in the `DECISIONS`
array of `html/scoring-rubrics.html`:

> 33. **TRPA decision (Nov. 2, 2026): debris flow exposure is mean upslope slope and burn
> severity, with contributing area as a gate.** The draft's drainage-area indicator (E2) is
> dropped as a weighted term: under 0.25 square miles scores 3, which was 4,798 of 5,096
> culverts, so it carried no information. Exposure is 0.40 slope and 0.60 severity, the draft's
> proportions without E2, and keeps its 0.70 share of vulnerability on culverts and bridges.
> Slope is sampled as before. Severity is the highest class covering at least 25 percent of the
> contributing watershed (culverts, with the 25 m buffer where no watershed exists) or of a 300
> ft buffer (roads and bridges), the wildfire rule of decision 27, in place of the maximum.
> Culverts and bridges with a contributing area over 3 square miles score 0 on exposure, so the
> pair reads Low on sensitivity alone; roads are not gated. The TRPA most-likely fire severity
> surface still stands in for predicted soil burn severity until the contracted package
> arrives, which then replaces it on the same breaks and the same 25 percent rule. Supersedes
> decision 16; amends decision 15 (option 2 Wildcat is compared in December, not substituted).
> Sensitivity unchanged.

If the cumulative share rule is chosen (section 1), say so in the severity sentence.

Elsewhere in `docs/SCORING_RUBRICS.md`:

- Line 3: Version 0.8, Nov. 2, 2026. The markdown has no version table or departures list; the
  departures table is in the HTML.
- 1.7 Sampling rule: add that debris-flow severity is sampled by area share, within 300 ft on
  roads and bridges (decision 33).
- 2.3 (DF-C) and 3.2 (DF-B): the "E1 to E3, 0.70 total" rows become "E1 and E3, 0.70 total".
- 4.1: "scored as the maximum along the segment" becomes slope as the maximum touching the
  segment, severity by area share within 300 ft.
- 4.2: the intro's road weights "(option 1: 0.29, 0.29, 0.43" become 0.40 and 0.60; "bridges
  (25 m or watershed)" becomes 25 m for slope and 300 ft for severity. The E2 (option 1) row
  becomes "gate, not scored" with the 3 square mile rule; weights shown as 0.40 and 0.60; the E3
  sampling reads "highest class covering 25 percent".
- 4.3: rewrite the first bullet (the slope raster is reused from the culvert delineation; the
  area raster is now the gate). Delete the second bullet (the drainage-area direction,
  "Intended"); decision 33 reverses it.
- 4.4: keep the Oct. 26 consultant paragraph as the record and add that decision 33 revised
  option 1 afterward.

## 3. Code changes, by file

### `config.yaml`

```yaml
  debris_flow:             # DF-C, DF-B, DF-R: decision 33, slope and severity, area as a gate (rubric 4.2)
    cell_m: 30
    weights: {e1: 0.40, e3: 0.60}   # e2 removed (decision 33); exposure keeps 0.70 of V through scoring.dfc / dfb
    buffer_ft: 300                  # E3 on roads and bridges: the share of a 300 ft buffer
    e1_buffer_ft: 0                 # roads: E1 keeps today's rule, the class touching the segment
    e3_min_share: 0.25              # E3: highest class covering at least this share (the wildfire rule, decision 27)
    e3_share_cumulative: false      # true: highest class k where class k or worse covers the share (open, section 1)
    area_gate_sqmi: 3.0             # culverts and bridges over this contributing area score exposure 0
    slope_fc: Hazard_DebrisFlow_Slope
    area_fc: Hazard_DebrisFlow_Area  # kept for the gate and the map; no longer scored
```

Rewrite the comment above `scoring.v_max_exclude` (lines 115 to 118): the reason is now the
stand-in severity and the section 5 review, not the drainage-size break. Leave the list as is
for the run; change it only in section 5.

### `scripts/surfaces_dfav.py`

- `build_debris_flow_surface()`: return only `e1` and `e3`, in both branches. The
  read-existing branch (lines 129 to 133) and the build loop (lines 172 to 179) both look up
  `w["e2"]`, which raises once `e2` leaves the config weights. Keep building and writing
  `Hazard_DebrisFlow_Area` (the map, and the bridge gate below), but do not return it as an
  indicator. Hints: `e1` `"profile:slope"`, `e3` `"watershed"`.
- Culverts gate on their own `contrib_area_ac`. Bridges gate on the largest contributing area
  within 25 m, read from the 2 m `facc` in `profile.work_gdb` with one small windowed read per
  bridge (`max_area_sqmi_near()`). As built Nov. 2: `Hazard_DebrisFlow_Area` cannot serve the
  gate because `dissolve_classes()` drops class 0 (over 5 square miles), so a bridge over a big
  river would read only the hillslope classes beside it, and the classed raster `df_e2_cls` was
  saved at 2 m (600 million cells).
- `df_area_score()` stays for the map legend and the gate; mark it "gate only" in its
  docstring.
- Update the module docstring (lines 3 to 14).

### `scripts/score_exposure.py`

- `share_class()`: add `cumulative=False`. When true, sum the class shares from the highest
  class down before applying the threshold. Wildfire keeps the default.
- New `sample_watersheds_share(cfg, surf, share, cumulative, log)`: overlay
  `CulvertWatersheds_inc` with `_tiled(surf)`, sum class areas per incremental zone, accumulate
  them up the tree (a `tree_sum` with `tree_max`'s traversal and `v += full[ch]`, run per class
  and once for zone area), divide by the accumulated zone area (not `contrib_area_ac`, so the
  numerator and denominator cover the same zones), and take the highest class meeting the
  share. 0 where none.
- `score_culverts()`, debris flow (lines 754 to 773): E1 from `basin_slope_pct` through
  `df_slope_score` as now; the `contrib_area_ac` to `df_area_score` branch goes. For an indicator
  with `min_share(...) > 0`, use `sample_watersheds_share()` and fall back to
  `sample_points(cul, g, point_buffer_m, share=...)` where no watershed exists.
- `E_DFC_src` today records only the first indicator's source, so a culvert whose E3 fell back
  to the buffer still reads full. Combine: `default` where E1 defaulted, `buffer` where E3 fell
  back, else `profile`.
- Gate, after E: where `contrib_area_ac / 640` is over `area_gate_sqmi`, set `E_DFC_hist` and
  `E_DFC_pt` to 0 and `DF_gate = 1` (else 0). Keep the e1 and e3 terms as sampled so the popup
  shows what was gated. `DF_gate` is SHORT.
- `score_bridges()`, non-flood branch (lines 829 to 840): an indicator with `min_share(...) > 0`
  samples within `sample_distance_m(cfg, hazard)` (300 ft) with the share; the others keep
  `point_buffer_m`. Only DF-B E3 changes; LS-B has no share key. Gate: where
  `max_area_sqmi_near()` is over `area_gate_sqmi`, `E_DFB_hist = 0` and `DF_gate = 1`; the area
  goes to the bridges CSV as `df_area_sqmi` for review.
- `score_line_assets()`: per-indicator distance. `<name>_buffer_ft` in the hazard's config
  overrides `buffer_ft` for that indicator; without it nothing changes, so wildfire is
  untouched. Without this, adding `buffer_ft: 300` would move road E1 from touching the segment
  to the maximum within 300 ft, which reads 2 to 3 on almost every mountain road. Update the log
  line that reports the distance.
- Old E2 fields: `ensure_fields` adds fields but never drops them, and `apply_by_key` writes
  only the fields listed, so `E_DFC_e2` on Culverts and `E_DFB_e2` on Bridges would keep their
  old values and publish beside the new E. For debris flow, delete `E_{pair}_e2` from both
  layers if present (`arcpy.management.DeleteField`) and log it. The roads table is rebuilt, so
  `E_DFR_e2` goes on its own.
- `DF_option` stays `"1 (severity stand-in)"`: the severity input is still the stand-in, which
  is what the field flags. Nothing to change at lines 791 and 816.
- Docstrings: the module docstring at line 19 ("Debris flow and avalanche plug in the same
  way") and the bridges line (line 24), and `hint_agg()`, which names DF E2.

### `scripts/score_vulnerability.py`

No change. The gate zeroes E, so V_DFC and V_DFB read 0.30 times sensitivity. `DF_gate` is
already on the layers from `score_exposure.py`; publishing is the next file.

### `scripts/publish_results.py`

`CULVERT_COLS`: remove `E_DFC_e2`, add `DF_gate`. `BRIDGE_COLS`: add `DF_gate`. `ROAD_COLS`
keeps `E_{p}_e2` (landslide and wildfire use it; columns are filtered by presence).

### `scripts/build_curated_gdb.py`

The print maps read `PROTECT_curated.gdb`, and its DataDictionary hard-codes the old method.

- `DF_LEFT_OUT` (lines 90 to 91): the reason becomes the stand-in severity pending the section 5
  review, not "nearly every asset scoring 3 on drainage size".
- `E_DFR_hist`, `E_DFC_hist`, `E_DFB_hist` (lines 328, 592, 764): 0.40 x e1 + 0.60 x e3, with
  the gate on culverts and bridges.
- Remove the E2 fields: `E_DFR_e2` (335 to 338), `E_DFC_e2` (598 to 601), `E_DFB_e2` (769 to
  771). Update the e1 and e3 descriptions (severity by area share, 300 ft on roads and bridges)
  and the weights in their `used=` text (0.40 and 0.60).
- Add `DF_gate` on culverts and bridges.
- `DF_option` values text (607, 776) reads "1 (fire severity stand-in)"; match the code, "1
  (severity stand-in)".
- `Hazard_DebrisFlow_Area` dataset (1157 to 1164): relabel as the gate, used by
  `score_exposure.py` for DF-B, not as E2.
- Roads copy (line 1280): drop `"E_DFR_e2"` from the `Exposure_debris_flow_roads` list.

### Pages and docs (mirrors)

- `docs/SCORING_RUBRICS.md`: section 2 above.
- `html/scoring-rubrics.html`: `PAIRS` and `DECISIONS` arrays, the departures table, the version
  tip at line 269 (v0.7 to v0.8). The weights row at line 367 is unchanged (E 0.7 / S 0.3).
- `Hazard_Asset_Pairs.md`: DF-B, DF-C, DF-R exposure text in the section 2 table and the
  "Debris-flow exposure option" paragraph (line 224); bump to v0.9. Mirror the `pairs` array in
  `html/reference-hub.html` and its mirror comment at line 348 (v0.8 to v0.9).
- `html/results.html`: `DF_TEXT` (539), the Overview `noteTip` (691), the DF-R note (697), the
  stand-in pairs note (747), the Debris flow tab note (985) and drainage text (986), the road and
  culvert popups (988, 989: drop the E2 fields, add `DF_gate` on culverts), the grid column for
  `E_DFR_e2` (1000), the "Drainage size (E2)" note (1004, becomes the gate note), and the help
  text (1219). If the pairs rejoin `V_max` in section 5, drop the "left out" clause in 539, 691,
  697, and 747.
- `html/results-simple.html`: the stand-in note (429), the Debris flow tab banner, lead, notes,
  popups, grid column, and footer (666 to 700).
- `html/results-guide.html`: the stand-in definition (230 to 232) and the debris flow method row
  (262 to 264).
- `html/references.html`: the data dictionary row at line 192 ("E: slope 0.2, drainage size 0.2,
  burn severity 0.3") becomes "E: slope 0.4, burn severity 0.6 (severity by area share); area
  over 3 sq mi gates culverts and bridges to 0". Remove the E2 field row (193). Add `DF_gate`.
- `print-maps/layers.yaml`: no area surface layer exists on either branch, so nothing to
  relabel. The debris flow exposure sheet shows the slope surface alone, which is now 40 percent
  of E; adding the severity surface is optional.
- `html/workshop-punchlist.html`: add a dated row for decision 33 under the surfaces lane; close
  the Oct. 15 drainage-size floor items (the decisions-open row at line 183 and the dated entry at
  255) and note decision 33 on the Oct. 12 ICF package row (252).
- Workshop deck (built outside the repo): the Step 2 table row for debris flow reads "Mean
  slope and drainage area from the 2 m lidar DEM, and burn severity". Change to "Mean upslope
  slope from the 2 m lidar DEM and burn severity by area share; large basins gated out". The
  deck notes in the Claude project (`claude/WORKSHOP1_DECK_NOTES_2026-10-29.md`) carry the
  same row.

## 4. Run order

1. Baseline: the published results at 909d8ef (`data/processed/results/culverts_results.geojson`,
   `bridges_results.geojson`, `roads_vulnerability.csv`) are the "before" for section 5. Pull any
   numbers you need from them before step 4 overwrites them.
2. `python scripts/score_exposure.py --hazard debris_flow --assets culverts bridges roads --overwrite`.
   No `--build`: the slope and area surfaces do not change, and `--build` reruns the 2 m
   slope-weighted flow accumulation. `--build` with no `--assets` scores nothing. A `--dry-run`
   first gives the class counts without writing. `Hazard_Wildfire_Severity` must exist (it
   does).
3. `python scripts/score_vulnerability.py --assets culverts bridges roads` (the default is
   culverts only).
4. `python scripts/publish_results.py` (also writes the hotspot counts).
5. `python scripts/build_curated_gdb.py --overwrite`.
6. Print maps: `print-maps/build_layers.py` only if `layers.yaml` changed, then
   `print-maps/print_maps.py check` and `export` for the debris flow sheets.
7. Pages and docs from section 3. Commit with the decision number in the message.

## 5. Review before touching `v_max_exclude`

Produce these before and after, and paste them into the commit or the punch list. Before is
909d8ef.

- Class shares per pair (Low, Medium, High) for DF-R, DF-B, DF-C, beside FL and LS on the same
  assets. Before, culverts: DF-C High 2,745, Medium 2,347, Low 4; LS-C High 1,768; FL-C High
  456. The section 1 ceiling for DF-C is 2,239 High with the gate.
- E3 on culverts: the distribution under today's maximum (1: 2,507; 2: 311; 3: 2,278), under
  the per-class share rule, and under the cumulative rule. This settles the open item in
  section 1.
- How many culverts and bridges the gate zeroes, listed by name for bridges. Before, 29 culverts
  have `contrib_area_ac` over 1,920 acres. Bridges over the Upper Truckee, Trout Creek, and the
  other large tributaries should be in the list; a bridge over a first-order ravine should not.
- `V_class_all` versus `V_class` on culverts: what share of assets changes class if the pairs
  rejoin `V_max`, and which pair they move from. Before, 2,251 of 5,096 differ, and DF-C sets
  `V_max_all` on 4,488.
- Roads over large rivers (the gate does not apply): read E1 at the Upper Truckee, Trout Creek,
  and similar crossings. On a channel cell, mean upslope slope is the whole basin's mean slope,
  so the touching maximum can come from the river rather than the hillslope. If it does, mask E1
  in the surface builder where the 30 m contributing area is over the gate, as a candidate for
  decision 34.
- The known sites from the Oct. 12 check (Northwood Blvd, the Washoe flash flood, Meeks Creek)
  and the July 14 hindcast sites on the storm events page: read High or Medium on the new pair,
  or say why not.
- The E floor: the count of culverts and roads with E_DF exactly 0.60 (Low severity, flat), and
  the class shares against the section 1 table. If Medium starts at a 10 percent slope on Low
  severity basin-wide, propose debris flow breaks the way wildfire got them, as candidate
  decision 34, and do not flip `v_max_exclude` until that is settled.

Only after that: empty `scoring.v_max_exclude`, re-run step 3 onward, and update the "left out"
text on `results.html`, `results-simple.html`, and `results-guide.html`, `DF_LEFT_OUT` in
`build_curated_gdb.py`, and the dictionary rows on `references.html`.

## 6. Timing

The Results page freeze is Nov. 4; Workshop 1 is Nov. 9. The surfaces already exist. New code
is the watershed share sampler, the per-indicator road distance, the bridge share and gate, and
dropping the old E2 fields; then the mirrors, which run to eight pages plus the curated
geodatabase. Bridge watersheds are left for December to keep this inside the freeze. The
section 1 ceiling says DF-C will likely still read High on more culverts than LS-C, so plan on
the fallback: ship the method change with the pairs still excluded from `V_max`, label the tab
accordingly, and finish the inclusion decision for December with the contracted severity and
the Wildcat comparison.

## 7. Note to ICF

Send after the run, with the before and after class shares attached:

> Debris flow exposure revised (TRPA decision 33, Nov. 2): the draft's drainage-area term is
> dropped as a score (it scored 3 on nearly every basin) and used as a gate: culverts and
> bridges with a contributing area over 3 square miles score 0 on exposure. Severity is sampled
> by area share, the highest class covering at least 25 percent of the contributing watershed
> for culverts and of a 300 ft buffer for roads and bridges, the same rule as wildfire. Slope is
> sampled as before. Exposure weights are the draft's proportions without the area term, 0.40
> slope and 0.60 severity, and exposure keeps its 0.70 share of vulnerability. Option 1 remains
> the structure; the TRPA fire severity surface stands in for predicted soil burn severity until
> the contracted package arrives, and Wildcat is compared in December. Sensitivity is unchanged.
> Class shares before and after are attached.

## 8. Open items carried forward

- Share rule, per class or "this class or worse", decided on the section 5 E3 numbers before
  the run is final.
- Whether debris flow gets its own class breaks, and whether roads over large rivers get the E1
  mask (candidate decision 34), decided on the section 5 numbers.
- Bridge watersheds for DF-B severity (December).
- DF-B span length direction (decision 12) is still the draft's; unchanged by this work.
- December: contracted predicted soil burn severity replaces the stand-in; `DF_option`
  becomes "1 (contracted severity)"; Wildcat run compared as option 2; the 2050 and 2080
  horizons.
