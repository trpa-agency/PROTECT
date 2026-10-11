# Archived pages

Pages moved out of the live site on Oct. 8, 2026. GitHub Pages runs Jekyll, which skips
directories whose names start with an underscore, so nothing in this folder is served at
trpa-agency.github.io/PROTECT. The files stay in the repo for reference; restore one with
`git mv` back to `html/`.

| File | Why it was archived | Replaced by |
|---|---|---|
| `criticality-index-hazards.html` | Fixed equal-weight copy of the Criticality Index with the same hazard filters. Two apps scoring the same network with the same sub-indices confused the landing page. | `html/criticality-index.html` (weights adjustable, hazard filters, CSV export) |
| `od-services-index-simple.html` | One-ranking, one-normalization demo of the OD Services Index built for the August 2026 Steering Committee. | `html/od-services-index.html` (the full app, now linked from the landing page) |
| `risk-index-tool.html` | Phase 1 MVP map of live TRPA layers with a per-component status view. Superseded by the Results page, which shows the scored assets; the December single-page app grows from Results instead. Archived Oct. 10, 2026. | `html/results.html` |
| `culvert-results.html` | Flooding results as a standalone page (culverts and bridges, drainage area on click). Folded into the Results page as its Flooding tab, Oct. 10, 2026. | `html/results.html#flood` |
| `wildfire-results.html` | Wildfire results as a standalone page. Folded into the Results page as its Wildfire tab, with the 300 ft sampling footprint layers, Oct. 10, 2026. | `html/results.html#wildfire` |
| `landslide-results.html` | Landslide results as a standalone page. Folded into the Results page as its Landslide tab, Oct. 10, 2026. | `html/results.html#landslide` |
