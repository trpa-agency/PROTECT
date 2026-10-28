# Consultant review of the results pages, Oct. 26, 2026: TRPA response

The consultant (ICF) reviewed the Criticality page, the Scoring Rubrics page, the Results page,
and the Workshop Feedback page on Oct. 26, 2026 and sent written comments. This is the record of
what TRPA did with each one. The rule applied: a wrong number or a broken control is fixed; a
presentation comment is taken unless it would make the page more technical for workshop
attendees; a method comment is adopted when it brings a reason, and recorded as a numbered
decision in `docs/SCORING_RUBRICS.md`; nothing is reopened that the rubrics already settle
without new evidence. Every change below landed Oct. 27, 2026 unless the status says otherwise.
Their responses to the numbered rubric decisions came in a separate spreadsheet and are not
covered here.

Status words: **Done** (on the page), **Scheduled** (code in the repo, needs a server run),
**Declined** (with the reason), **Recorded** (no change needed, noted in the rubrics).

## Criticality page (`html/criticality-index.html`)

| Comment | Response | Status |
|---|---|---|
| Title the map "Criticality Assessment"; keep the weighting sliders or make a final choice? | The page is now titled Criticality Assessment. The default weights (traffic 0.3, detour 0.3, access to critical services 0.3, equity 0.1) are the method of record and are stated in a plain paragraph with three example scenarios; the sliders sit inside a collapsed "Test other weights" block. | Done |
| Rename "criticality" in the color-by to "overall criticality" | Renamed. | Done |
| Traffic, detour, and access to services show two quartiles, not four; map the real values | The cause was that those inputs arrive as Jenks class scores, most of them in the lowest class, so rank quarters collapsed. Detour is now colored by the added detour distance in miles (0, under 0.1, 0.1 to 0.5, 0.5 and over) and access by residents routed (0, under 10, 10 to 100, 100 and over). Traffic is published only as a volume class, grouped 1, 2 to 3, 4 to 6, 7 to 10 and labeled as such. The chart bins the same way. | Done |
| Rename "criticality class" to "criticality score" | Not adopted as worded: the score is the continuous value and the class is its quarter, and both appear on the page. The class is now called the criticality quarter everywhere, which says what it is. | Declined, renamed instead |
| Miles by class shows two bars | Same cause as the quartile comment; the chart now follows the view's four classes with the legend's labels. | Done |
| "Segments that tie share a rank" unclear | Rewritten: when many segments share the same value they share a rank, so a quarter can hold more or fewer than a quarter of the segments. The percentile is now tie-averaged to match. | Done |
| Too busy: remove the z-score versus min-max choice; hazard filter only on overall criticality | The normalization choice is gone; z-score is the method. The hazard filter stays on every view because reading a component inside a hazard footprint is what the filter is for; it is one control. | Done, partly |

## Scoring rubrics (`html/scoring-rubrics.html`, `docs/SCORING_RUBRICS.md`)

| Comment | Response | Status |
|---|---|---|
| Flood exposure approach for culverts and bridges makes sense; NHD flowline as exposure 1 supported | Concurrence recorded in decision 31. | Recorded |
| Add a 10 to 30 m buffer around the 500-year floodplain as exposure 1 for every asset type | Adopted as decision 31: a 20 m band around the FEMA zones scores 1 on every flood pair (`exposure.flood.near_zone_buffer_m` in `config.yaml`, built by `scripts/score_exposure.py`). It takes effect at the next flood run on the server, which rescores the five flood pairs and republishes; until then roads have no class 1, which is why the road flood map shows no Medium. | Scheduled |
| Landslide roads: embankment condition or stabilization locations from the DOTs as a sensitivity indicator, if available | Recorded in section 6.5. It would be the first road sensitivity term and would revisit decision 25 for that pair only; it depends on the asset-condition request to the state DOTs. | Recorded |
| Landslide (other assets), debris flow option 1, avalanche consistent with the original recommendation | Recorded in sections 3.5, 4.4, and 5.4. | Recorded |

## Results page (`html/results.html`)

| Comment | Response | Status |
|---|---|---|
| "Priority" unclear against criticality and hotspots | The view is now Highest vulnerability: color only, no line weight, no multi-term text. Criticality is its own view and the Hotspots filter is the one place the two are read together. | Done |
| Debris flow Medium or High almost everywhere; expect overlap with landslide | Known and already handled: the stand-in debris-flow pairs are left out of the combined class (`scoring.v_max_exclude`), and the view's note says why. Revisited with the USGS Wildcat run (decision 15). | Recorded |
| Assets on the boundary with slight partial intersections are included; is that TRPA's preference? | Yes. A road that crosses the boundary is still a route people use; clipping would split segments and change criticality. The street network is used as built. | Recorded |
| Map is busy and technical; fewer tabs, buttons, and toggles; a downloadable 2-pager | The tab per hazard stays (it is what makes the page readable); the clutter inside the panels was cut: one color view on Landslide and Debris flow, the flood exposure button dropped, Design storm nested under the culvert views, every control labeled by the assets it changes. The two-page guide is `html/results-guide.html`, linked from the header, the How to use dialog, and every Pages menu. | Done |
| Overview color-by changes roads only | Every view now colors every asset layer it scores; an asset with no pair for the selected hazard draws gray and the note says which assets each hazard scores. | Done |
| Exposure and sensitivity component scores in the popup | Every popup now gives each hazard's score with its class and names the hazard that set the asset's class; culvert and bridge popups carry exposure E and sensitivity S for flooding, and the hazard tabs' popups carry the exposure terms behind each score. | Done |
| Roads, paths, and transit hubs have no legend on the Overview | Each layer row now shows its symbol (solid line, dashed line, dot, square, small square) and the color legend under the view applies to all of them. | Done |
| Culvert drainage area stays on the map after deselecting | Fixed: a click anywhere else clears it, and turning the culverts layer off clears it. | Done |
| Priority map should show only Low, Medium, High; remove line thickness and its text | Done, with the rename above. | Done |
| Culvert "i" as a complete sentence | "The culvert's score is the highest among flooding, landslide, and debris flow. Only public jurisdictions are scored." | Done |
| What is "Set by"? | Renamed Highest hazard, shown as the hazard's name (Flooding, Wildfire, and so on) instead of the pair code, in popups and the table. | Done |
| Popup scores are only numbers; show the class and the components | Each hazard score reads as "score (class)" in every popup. | Done |
| Key for what a score of 1.6 means; bring the cutoffs to the top | The class cutoffs sit directly under the legend on every tab and in the How to use dialog. | Done |
| Apache Ave has three paths | Checked: the active transportation source has three facilities on that street (a class 1 bike lane, a class 2 bike lane, and a pedestrian path), so the count is the source's. One sits in the 500-year zone and two do not, which points at geometry offsets on the same street; flagged for the network lane. | Recorded |
| Only eight transit hubs; TRPA had wanted maintenance facilities included | Open question for the transportation team; the eight are the transit centers in the TRPA Transportation service. Not changed for the workshop. | Open |
| The Criticality view mixes road criticality with other assets' vulnerability; consider removing criticality from the Results page | In the Criticality view the other assets now draw gray. Criticality stays on the page because the Hotspots reading needs it beside vulnerability; the full index is on the Criticality Assessment page. | Done, partly |
| Report road percentages by miles, not segments | Every road and path figure on the page is by miles: key numbers, the asset-type chart, the vulnerability-by-criticality matrix, and the criticality chart. By segments 21.5 percent of roads are High; by miles 41 percent are. | Done |
| Remove criticality from the summary graphics | The asset-type chart is vulnerability only. One chart, road miles by vulnerability within each criticality quarter, stays because it is the hotspot reading. | Done, partly |
| The asset-type chart and key numbers should follow the selected hazard, by miles | They do: picking a hazard above the map redraws the key numbers and the chart for that hazard. | Done |
| Flooding: only High and not exposed roads; where are Medium and Low? | By construction: a road's flood class is 0, 2, or 3, so its vulnerability is High or not exposed. Class 1 did not apply to roads. The page now says so, and decision 31 (the 20 m band) adds a class 1, which is the Medium. | Done, Scheduled |
| The flood buttons do not change roads; nest them under culverts | The design storm control is now headed "Culverts: design storm", sits under "Culverts, colored by", and its tooltip says it changes culverts only; the roads row says the same. | Done |
| Culverts: only the final vulnerability as an option, floodplain as a reference layer | Vulnerability is now the default culvert view and the Flood exposure button is gone (the flood surface layer shows that). Storm vs capacity stays as the second view: whether the pipe passes the storm is the question attendees ask first. | Done, partly |
| Rename "Classed flood surface" | Now "Flood zones and streams, as scored", with a labeled legend. | Done |
| Will the final version map every asset class under every hazard? | Each tab maps the assets that hazard scores (the 15 pairs). The Overview's hazard views show every asset, gray where there is no pair, and the notes list which assets each hazard scores. | Recorded |
| Proprietary data: can fire severity and likelihood be shown publicly? | The layers shown are public (Sierra Nevada Regional Resource Kit burn probability; TRPA fire severity). The contracted wildfire package's license is checked before anything from it goes on the page; punch list item for Nov. 2. | Open |
| Wildfire legends missing for paths and three surface layers | Added. | Done |
| Landslide and Debris flow: "Colored by" does not name the asset; roads did not seem to change | The heading now reads "Roads, culverts, and bridges, colored by vulnerability" and there is one view, so there is nothing to toggle; the exposure classes are in the popups and the Susceptibility surface layer shows the ground. | Done |
| Debris flow exposure and vulnerability nearly equal for culverts | Expected: sensitivity (opening size and condition) defaults on most culverts. Recorded; revisited with the Wildcat run. | Recorded |
| Avalanche: many roads missing on Slope tier | Roads with no ground above them within 1,000 ft had no tier value and were not drawn; they now draw as tier 0 and the legend says so. | Done |
| Avalanche: no overall vulnerability view | Vulnerability is now the default view (for this pair it equals the exposure score, which the note says). | Done |

## Workshop Feedback page (`html/workshop-feedback.html`)

| Comment | Response | Status |
|---|---|---|
| Add a legend for roads, culverts, bridges, and the rest | Added to the panel. | Done |
| Put "Data mapped:" before each station's data sentence; reword the wildfire question | Done as written: "Which roads, paths, and transit stops are at risk or leave people isolated if damaged?" | Done |
| How would a user know an asset is missing from the draft results without flipping between pages; color the assets by vulnerability and hazard | The assets are now colored by the selected station's hazard vulnerability class, the same classes and colors as the Results page, so "missing from the draft results" is read against what is shown. | Done |
| Make the discussion questions step 3; remove "Your notes" | The questions are step 3 with full presence. Your notes stays as step 4: it is the list that gets sent and holds the Send button. | Done, partly |
| Clear the entry form after a note is sent | Done. | Done |
