# VA review brief: the Nov. 2 to 3 runs

For the VA lead (streets, criticality, OD, RA2CE), from the TRIP lead. What changed in the
vulnerability assessment over Nov. 2 and 3, 2026, the five decisions behind it, where the
numbers landed, and what needs a second pair of eyes before the Nov. 9 workshop.

Everything is on branch `mtb-arc11` (commits c647d43 through bd06488, results in 99715e7,
ce4f2ef, and 99d13ac). No pull request is open. GitHub Pages serves `main`, so the live Results
page still shows the October results until the branch merges; preview the branch on the
`protect-root` server (port 8012) or read the tables in `data/processed/results/`.

## 1. What happened

The debris flow pairs were rescored (decisions 33 and 34), brought into the combined class
(35), and the question "why did the combined High not narrow" turned up two things that had
nothing to do with debris flow: the flood run had never been redone after the stream-crossing
decision of Oct. 28 (32), and landslide was still scored on the watershed maximum (fixed by 36).
Both were rerun Nov. 3. A last check showed the "highest hazard" label naming a pair whose own
class was below the combined class, so the label rule changed (37).

Six server steps ran Nov. 3 (flood build 5 min, landslide 1.5 min, debris flow bridges 1 min,
vulnerability 1.5 min, publish 6 min, curated geodatabase 10.5 min). The debris flow surface
build itself took 4 h 44 min on Nov. 2 because the environment cell size stayed at the 2 m flow
accumulation grid; c647d43 pins it to 30 m, so the next `--build` should take minutes. That fix
is unverified until the next build.

## 2. The decisions

Each is written up with its reason and its numbers in `docs/SCORING_RUBRICS.md` v0.10 (the
Scoring Rubrics page mirrors them under Decisions). Short form:

- **32 (Oct. 28, run Nov. 3): a stream crossing scores 1, not 2, on every flood pair.** At 2,
  a segment touching the 10 m band around a mapped stream anywhere along its length read High,
  since roads carry no sensitivity. Config `exposure.flood.stream_class: 1`. High flood road
  miles 287 to 43; 2,002 segments moved to Medium; FL-C High 753 to 439.
- **33 (Nov. 2): debris flow exposure is 0.40 mean upslope slope plus 0.60 burn severity,
  with contributing area as a gate.** The draft's drainage-area term scored 3 on 4,798 of
  5,096 culverts, so it carried nothing. Severity is the highest class covering a quarter of
  the drainage (culverts) or a 300 ft buffer (roads, bridges), the wildfire rule. Culverts and
  bridges draining more than 3 square miles score exposure 0 (`DF_gate`: 29 culverts, 22 of
  40 bridges). The TRPA most-likely fire severity surface still stands in for soil burn
  severity.
- **34 (Nov. 2, confirmed Nov. 3): debris flow classes on 1.5 and 2.0.** With the stand-in
  severity Low over most of the basin, the shared 1.0 break read Medium on any slope over 10
  percent. Three bridges are gated by hand (the two SR 89 bridges at the Truckee River outlet,
  where the lake is a sink in the DEM, and Lake Tahoe Blvd over Angora Creek, read at 2.89
  square miles by the 25 m window just downstream of the gated View Circle bridge at 3.30).
  Channel cells draining over 3 square miles are masked to 0 in the slope surface so river
  crossings do not inherit the whole basin's slope.
- **35 (Nov. 3): the debris flow pairs count in the combined class.** `scoring.v_max_exclude`
  is empty. The class shares now sit with the other hazards (culverts 41 percent Medium or
  High against 47 for flooding and 53 for landslide; roads 20 percent against 24 for wildfire,
  16 for landslide, and 15 for flooding). `V_max_all` and `V_class_all` stay in the tables and
  equal the main fields.
- **36 (Nov. 3): landslide susceptibility by area share.** The maximum rule let one 90 m cell
  over 80 percent prone, or one recorded landslide, anywhere in a drainage score 3. E1 is now
  the highest class covering a quarter of the drainage (culverts), of the 25 m buffer
  (bridges), or of the segment's own length (roads). Config
  `exposure.landslide.e1_min_share: 0.25`; roads needed a buffer-0 share branch in
  `sample_lines`. Culverts at class 3 1,853 to 1,370; LS-C High 1,808 to 1,340; LS-R High
  1,572 to 1,261 segments, 221 to 160 miles. Side effect to weigh: a recorded landslide
  covering less than a quarter no longer scores 3 on its own.
- **37 (Nov. 3): the highest hazard is the pair that sets the class.** Wildfire and debris flow
  carry their own breaks, so the pair with the top score was not always the pair with the top
  class: 426 culverts and 309 road segments read "from debris flow" at Medium while their
  debris flow class was Low. `V_max_pair` now names the pair with the highest class, ties by
  score, and `V_max` is that pair's score. `V_class` is unchanged. Verified on the public
  tables: zero mismatches after the publish.

## 3. Where the numbers landed

Public tables, Nov. 3 evening publish (99d13ac). Before is the October publish ICF reviewed
on Oct. 26.

| | Before | After |
|---|---|---|
| Roads High, all hazards | 4,951 segments, 436 of 984 miles (44 percent) | 3,749 segments, 297 miles (30 percent) |
| Roads Medium / Low | 2,486 / 10,848 | 3,740 / 10,796 |
| Hotspots (High on the top criticality quarter) | 1,131 | 683 |
| Culverts High / Medium / Low | 1,905 / 1,297 / 1,894 | 1,774 / 1,327 / 1,995 |
| Bridges High / Medium / Low | 3 / 35 / 2 | 8 / 29 / 3 |
| Flooding, roads High | 2,668 segments, 287 miles | 666 segments, 43 miles |
| Landslide, roads High | 1,572 segments, 221 miles | 1,261 segments, 160 miles |
| Landslide, culverts High | 1,808 | 1,340 |
| Debris flow, culverts Medium or High | 5,021 (99 percent) | 2,096 (41 percent) |
| Debris flow, roads Medium or High | 9,075 (50 percent) | 3,590 (20 percent) |

Per pair on roads after the run (18,285 segments):

| Pair | Low | Medium | High | High miles |
|---|---|---|---|---|
| WF-R | 13,888 | 2,660 | 1,737 | 124 |
| DF-R | 14,695 | 1,913 | 1,677 | 128 |
| LS-R | 15,831 | 1,193 | 1,261 | 160 |
| FL-R | 15,617 | 2,002 | 666 | 43 |
| AV-R | 17,832 | 442 | 11 | 1 |

Which pair sets the class (`V_max_pair`): roads WF-R 12,449, DF-R 2,859, FL-R 1,577, LS-R
1,307, AV-R 93 (on the 10,796 Low segments the tie goes by score: wildfire takes 9,683, since
its score is at least 1.0 everywhere, and debris flow the other 1,113, from the slope term);
culverts DF-C 3,054, LS-C 1,165, FL-C 877; bridges FL-B 29, DF-B 9, LS-B 2.
Paths are 216 with 62 High; transit hubs eight with one High.

Combined class by criticality quarter (roads):

| Criticality quarter | High | Medium | Low | High share |
|---|---|---|---|---|
| 3 (top) | 683 | 928 | 2,986 | 15 percent |
| 2 | 583 | 665 | 3,212 | 13 percent |
| 1 | 1,024 | 1,084 | 2,333 | 23 percent |
| 0 (bottom) | 1,459 | 1,063 | 2,265 | 30 percent |

One reading: the top quarter runs along the lake and through the valley bottoms, where the
slope-driven hazards are weakest, so the hotspot count is small partly by geography. Worth a
look before the workshop frames "where the vulnerable, critical roads are."

## 4. What to review

In your lane:

1. **The share rule on roads (decision 36) depends on segment length.** E1 is the highest
   landslide class covering a quarter of the segment's own length, so a short segment reaches
   the bar with a few meters of prone ground and a long one needs a quarter of its run. Check
   whether the segment length distribution in the clean street layer makes that fair, or
   whether the rule should be length-capped (a fixed window) the way culverts use the
   drainage. Same question applies to wildfire severity (decision 27) and debris flow severity
   (33), which sample roads on a 300 ft buffer instead.
2. **The criticality-by-class table above.** If it holds, the Results page's hotspot framing
   and any RA2CE scenario selection should say so plainly. If it does not hold (for example
   the quarters are percentile cuts that bunch the lake ring), say which cut to use.
3. **Active transport key.** Paths are keyed on the Transportation service's OBJECTID
   (`at_id`). The service gained OBJECTID 1668 (Tahoe Valley Greenbelt) on Oct. 7, after the
   October wildfire run, so the publish wrote 215 paths while the curated layer had 216. Fixed
   by rerunning wildfire for paths and hubs, but the key is fragile. Is there a stable id on the
   paths layer, or should paths join the street network of record (`src_objectid`)?
4. **Freeze the street network before Nov. 9.** Every exposure table is keyed on the clean
   street layer's `src_objectid` and the published geometry (`roads_geometry.geojson`, 5 m
   simplify). Any rebuild means rerunning every hazard and the criticality join.
5. **RA2CE and the criticality app.** `V_max` changed meaning on Nov. 3 (it is now the
   class-setting pair's score, not the top score across pairs). Anything downstream that
   ranks or filters on `V_max` should use `V_class`, or the per-pair `V_<pair>_hist` fields,
   instead. The criticality app and QA page read only the criticality tables and are
   unaffected.

Already put to ICF (review request, comments asked by Nov. 6; TRPA makes the calls):

- Decision 36: whether a quarter of the drainage is the right threshold, and whether a
  recorded landslide covering less than that should still count on its own (today it does
  not; one config line and a landslide rerun if we want it to).
- Decision 35: whether the stand-in severity belongs inside the combined class until the
  contracted burn severity package arrives.
- Decision 34: the 1.5 lower break for debris flow.

If you disagree with any of the three, say so before ICF replies so one answer goes back.

## 5. Where things are

- Rubric: `docs/SCORING_RUBRICS.md` v0.10, decisions 32 to 37 (sections 1.4, 2.8, 4.4, 6.5).
  Page mirror: `html/scoring-rubrics.html` v0.10.
- Results: `html/results.html` (Overview, Flooding, Landslide, Debris flow tabs carry the new
  notes and the three hand-gated bridges); `html/results-simple.html`, `html/results-guide.html`,
  `html/references.html`, and `html/index.html` mirror the text.
- Punch list: `html/workshop-punchlist.html`, four Nov. 3 rows, all Done.
- Record of the run: `docs/DF_METHOD_HANDOFF_2026-11-02.md` (the plan, marked executed).
- Code: `scripts/surfaces_dfav.py` (30 m build, saved aggregates), `scripts/score_exposure.py`
  (buffer-0 share branch), `scripts/score_vulnerability.py` (`_finish.roll`, decision 37),
  `scripts/build_curated_gdb.py` (field descriptions, debris flow in the across-pairs fields).
- Config keys: `scoring.v_max_exclude`, `scoring.v_breaks_debris_flow`,
  `exposure.flood.stream_class`, `exposure.landslide.e1_min_share`,
  `exposure.landslide.e1_share_cumulative`, `exposure.debris_flow.gate_bridge_ids`,
  `exposure.debris_flow.e1_mask_over_gate`.
- Still open: the debris flow build fix is unverified until the next `--build`; print maps
  after the curated geodatabase rebuild; the branch has no pull request.
