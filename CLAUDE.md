# CLAUDE.md - PROTECT

Project-specific overlay on `Documents\GitHub\CLAUDE.md`. Slim by design.

## What this repo does

The website for the whole **PROTECT** grant (public name Connecting Tahoe), not only the
vulnerability assessment. PROTECT = FHWA *Promoting Resilient Operations for Transformative,
Efficient, and Cost-saving Transportation* grant. The draft revised scope (Oct. 2026) has four
parts, and the site is organized by them in scope order: Task 1 **stakeholder engagement**; 2a
**lessons from past emergencies** (response audit of the Angora, Tamarack, Caldor, and Davis fires
and winter storms); 2b the **Tahoe Resilience Improvement Plan (TRIP)** (review of existing plans,
risk index ratings = the vulnerability assessment, pinch points and priority zones, projects and
funding strategy, additional needs); Task 3 the **Regional Emergency Communications and
Transportation Plan** (public name: transportation communications strategy). TRPA leads TRIP with
ICF. The older numbering (Task 3 = RIP, 3.2 = VA, 3.3 = mapping tool) survives in some docs and
tooltips; page copy uses names, not task numbers, until the scope is final.

The assessment follows a **three-step approach built on FHWA VAST guidance**: (1) criticality, (2) a
system-wide indicator screening of 15 hazard-asset pairs scored as
**Vulnerability = (Exposure x wE) + (Sensitivity x wS)** on 0-3 indicator scores with weights set
per pair (ICF draft VA Methodology, Aug. 20, 2026; rubrics in `docs/SCORING_RUBRICS.md`), with
criticality carried separately rather than as a multiplier, and (3) RA2CE disruption scenarios.
Do not reintroduce Asset Value or Adaptive Capacity as sub-indices. Current artifacts: the project pages index (`html/index.html`, v0.9,
a section per part of the grant scope, the TRIP work plan table, a Workshop 1 banner, and phasing); the **Workshop 1 punch list**
(`html/workshop-punchlist.html`: one dated task table with status in the page data, decisions
open, the print-map spec; it replaced `docs/WORKSHOP1_PUNCHLIST.md` on Oct. 8, 2026, and the
scripts, data paths, and references moved to the appendix of `docs/WORKSHOP1_BUILD_PLAN.md`); a reference hub (`html/reference-hub.html`, v0.6) with
tabs for the hazard-asset pairs, the source-of-record data and model inventory, framework/methods
(incl. a hazard impact & sensitivity matrix), and the exposure dataset evaluation; the **Scoring
Rubrics page** (`html/scoring-rubrics.html`, v0.4: interactive per-pair scoring for all 15 pairs
on the consultant's half-point scale, rubric tables, framework, 24 decisions, and the list of
TRPA departures from the Aug. 20 draft; mirrors `docs/SCORING_RUBRICS.md`). **No flood depth
model is being acquired (Oct. 8, 2026):** flood exposure is FEMA zones and stream crossings on
every page; never describe a flood model as purchased or pending. The **Vulnerability Assessment page** (`html/vulnerability-assessment.html`, Oct. 10, 2026) is the front door for the assessment: one data-driven page with an Overview tab (every asset's V_max class, vulnerability by criticality, hotspots) and one tab per hazard (flooding with the drainage area on click, wildfire with the 300 ft sampling footprint layers and a segment-buffer click, landslide, debris flow, avalanche), each a config block in the page (`MODES`) that swaps data files, legends, renderers, charts, and table columns in one map, one grid, and two chart divs. It reads `data/processed/results/` written by `scripts/publish_results.py`; a hazard whose files are not published shows an empty state. The standalone hazard pages and the Phase 1 MVP map are archived. Every page carries a **Pages menu** at the right of its header (a native `details.pages` dropdown, Oct. 13, 2026; it replaced the separate site nav row), grouped by part of the grant scope since Oct. 26, 2026: Home and All pages; Engagement (Workshop 1 punch list, Vulnerability Assessment Feedback); Lessons from past emergencies (the **Baseline Assessment** summary, `html/baseline-assessment.html`, Oct. 28, 2026: ICF's Oct. 13 draft Baseline Assessment and Incident Review, its 14 findings, and 14 TRPA-proposed actions in page data `FINDINGS` and `ACTIONS`; the report's recommendations section is still empty, so the actions are labeled proposed); Resilience plan (TRIP) (the Vulnerability Assessment, the **Criticality Assessment app** (`html/criticality-assessment.html`, live, 18,285 segments), the **Criticality QA** page (`html/criticality-qa.html`, Oct. 30, 2026), the **OD Services Index** (`html/od-services-index.html`), scoring rubrics); TRIP data and evidence (the **References** page, `html/references.html`, Oct. 28, 2026: glossary, the Results data dictionary moved out of the Vulnerability Assessment Guide, and sources with metadata links, all in page data `GLOSSARY` and `SOURCES` plus the static dictionary table; reference hub, climate inputs, historic hazards, storm events). The communications strategy gets a menu group when its first page lands. **Adding a page for any part:** put it in `html/` with the standard header, add it to its group in every page's menu (same markup on all pages, `class="on"` on its own link), add a card in its part on `html/index.html`, and replace the matching dashed "Coming" card on the root home page. URLs of existing pages do not change. Retired pages live in `html/_archive/` (see `ARCHIVED.md` there);
Jekyll skips underscore directories, so nothing in it is served by Pages.

**Draft gate (Nov. 6, 2026):** `html/gate.js`, loaded in the head of every page (`html/gate.js` from the
root home), is a soft gate for pages still under review. Its `GATED` list (today: All pages
`html/index.html`, baseline assessment, criticality QA, results-simple, workshop punch list, access to
services, scoring rubrics, reference hub, climate inputs, historic hazards, storm events, Vulnerability
Assessment Feedback; public: Home, Vulnerability Assessment, Vulnerability Assessment Guide, Criticality
Assessment, References) names the pages that show a navy
sign-in screen instead of their content, drop out of every Pages menu (a group left empty hides too),
and lose their cards on `html/index.html` and the root home (`a.page-card`, `a.tool`, the Vulnerability Assessment band's
`a.band-btn`, a QR `.tile` on the Vulnerability Assessment Guide; an emptied card grid hides with its heading). Pages are matched by full URL resolved against the script's folder, so
"index.html" in the list is All pages, never the public home. A padlock button sits just before
`details.pages` in every header: closed lock = staff sign-in, orange open lock = signed in, click to
sign out. The sign-in card also has a Request access mailto to gis@trpa.gov. The passphrase is stored
only as a SHA-256 hash (`HASH`); signing in keeps the hash in localStorage, and gated links in the
menu get an orange Draft pill once signed in. A second list, `DRAFT`, names public pages that are still
drafts (the Vulnerability Assessment and its Guide): always listed, with a TRPA Blue Draft pill. The pills
are real spans, and gate.js widens every Pages menu to 320 px so the longest label and pill fit on one line. Gate a page by adding its file name to `GATED`; release
it by removing the name; rotate the passphrase by replacing `HASH` with
`await protectGate.hash("new phrase")` from any page's console (a new hash signs everyone out).
It is not security: the repo is public and the files are served regardless, so it keeps drafts out of
sight for casual visitors and nothing more. Anything sensitive stays out of the repo, gated or not.

**Page renames (Nov. 8, 2026):** Results became the **Vulnerability Assessment**
(`html/vulnerability-assessment.html`), Results guide the **Vulnerability Assessment Guide**
(`html/vulnerability-assessment-guide.html`), Criticality the **Criticality Assessment**
(`html/criticality-assessment.html`), and Workshop feedback the **Vulnerability Assessment Feedback**
page (`html/vulnerability-assessment-feedback.html`). The old files (`results.html`, `results-guide.html`,
`criticality-index.html`, `workshop-feedback.html`) are redirect stubs that carry the query and `#tab`
hash across, so printed QR codes and shared links keep working: never delete them or reuse those names.
Menu labels are sentence case ("Vulnerability assessment"), titles and h1s title case. The ArcGIS Online
service names ("PROTECT Workshop Feedback notes", "... flood areas v2") and the localStorage keys keep
their old names on purpose. The public home's criticality card keeps its plain heading, "Which roads
matter most".

**Public home page (Oct. 26, 2026):** the repo root `index.html` is the project home, rebuilt from
the Connecting Tahoe story map collection (story item `6b67742ea10b44a2aedc6cdee909b59e`; Survey123
form `5f9c9adfb4c14f509937c6462d89fa65`, loaded in place on click). Images live in
`html/img/home/` (resized, EXIF stripped). It is what `trpa-agency.github.io/PROTECT/` serves, and it is
the intended target of `trpa.gov/resilienttransportation`, which is a 301 redirect on trpa.gov
(today it points at the story map collection), not a GitHub custom domain. The page is written for
the public: the story map's copy in house style (plus a lessons-from-past-emergencies step from the
draft scope), an Explore section with one block per part of the grant scope (live pages as cards,
dashed "Coming" cards for what is not built yet), and no task lists or open decisions. In every Pages menu, Home is `../index.html` and the old landing page
`html/index.html` is "All pages".

## Project context

- **Tool vision** (per `PROTECT_RiskIndexTool_Scoping_v0.1.docx`): a map-centric single-page app
  (Map / Charts / Table / Methods / About). Phasing: Phase 1 MVP ~mid-June 2026, **first Steering
  Committee Aug 2026** (nothing in October), Workshop 1 Nov 2026, VA + tool final Dec 2026,
  Workshop 2 May 2027, final RIP 2027.
- **Two-repo future**: the scoping doc proposes `protect-risk-index` (Python ETL) +
  `protect-risk-index-tool` (frontend, GitHub Pages). Neither exists yet; this single `PROTECT` repo
  is the working hub until the MVP build starts.
- **Disruption-risk tool decision**: **RA2CE (Deltares) selected** (Aug 2026); Volpe RDR evaluated
  and not pursued. Analysis work lives in `scripts/ra2ce`.
- **Partners**: ICF is the consultant (climate resilience); TRPA Science & Data + Transportation
  teams lead. The data team built a street network from Overture data (the base network for RA2CE)
  and the interactive Criticality Assessment app on top of it.
- **MVP build**: the MVP Risk Index Tool is built in this repo's `html/` folder using the TRPA
  dashboard stack (Calcite + ArcGIS Maps SDK + Plotly + AG Grid).
- **Hosting / visibility**: GitHub Pages for now (`trpa-agency.github.io/PROTECT`); final home is
  `data.trpa.gov/PROTECT`. Internal review draft only - do NOT commit raw internal source docs
  (xlsx/docx/pptx) or publish broadly yet. `_config.yml` (Oct. 28, 2026) limits the site to
  `index.html`, `html/`, and `data/processed/results/`; Pages had been rendering every `.md`
  (this file and `docs/`) as a web page. A new top-level folder or a new file under `data/` is
  served unless it is added to the `exclude` list. The repo itself is public on GitHub either way.

## Data sources (TRPA REST)

Base: `https://maps.trpa.org/server/rest/services` (use `/server/`, not `/arcgis/`; add `?f=pjson` to
inspect). Append `/<ServiceName>/<MapServer|FeatureServer>`; confirm the layer index per service.

- **Live:** `Transportation_Equity_Analysis_Tessellation` (Equity, FeatureServer), `Demographics`,
  `Avalanche_Zones`, `Fire`, `Streams_and_Flood_Zone`, `Vegetation_Burn_Severity`,
  `Transportation` (sublayers: Transit Network /5, Community Priority Zones /6, Active Transport /3),
  `Parcels`, `Boundaries`, `Emergency_Services`, `Forest_Health_*`, `Impervious_Surface_*`.
  Note: `Transportation_SMART` is traffic cameras, not road centerlines; road centerlines are not yet
  a standalone service (part of the Building Assets service).
- **Building:** a consolidated **Assets** service (roads/bridges/culverts + condition), packaged
  **Hazards** services, and a **WEPP** erosion/sediment service (post-fire; feeds debris-flow/flood exposure).
- **Needed (not created):** Landslide, Debris Flow, Earthquake, Wind, Winter Storm hazard layers;
  asset-condition (Caltrans/NDOT request).
- **External (non-TRPA):** FEMA NRI, HIFLD, Cal-Adapt, Climate Engine, USGS StreamStats. Competitive commercial data vendors (mobility, fire, flood, climate, geohazard, asset
  condition, multi-peril cat) are NOT named on the public pages - the researched landscape + outreach
  candidates live in `data/vendors.csv` (gitignored) and the project memory (`reference_data_vendors`).
  Keep only open-source / public / sole-source tools in the HTML; do not enumerate commercial vendor
  names in committed files.

- **RESTRICTED: NDOT SAM21 stormwater export** (`config.yaml` `ndot:` block). Shared under a
  sensitive/restricted data sharing agreement (executed Aug. 12, 2026, term through Dec. 31,
  2027; one named Data Steward). It lives on TRPA storage (F:) and is read in place by
  `scripts/ndot_culverts.py` into the analysis geodatabase only. Never copy it, or anything
  derived from it at the asset level, under the repo (`data/processed` is git-tracked and
  served by GitHub Pages), into `outputs/`, onto any html page, or into a public REST service.
  Segment-level aggregates are allowed but must be attributed to NDOT and reviewed by NDOT
  before publication. The `.gitignore` blocks `*ndot*` as a backstop. A public culvert that shares
  its crossing with an NDOT culvert publishes without the fields pooled over the crossing's barrels
  (`va_common.CROSSING_POOLED` and the loading ratios, Oct. 28, 2026): those let the NDOT barrel's
  capacity be subtracted back out.

The live readiness tracker is the Data and Model Inventory tab of `html/reference-hub.html`.

## Where things live

```
PROTECT/
├── index.html                       # public project home (Connecting Tahoe story rebuilt); images in html/img/home/
├── data/                            # input data, intermediate files
├── docs/                            # methodology, build notes, scoping archive
├── html/index.html                  # v0.9 project pages index: a section per scope part, TRIP work plan, Workshop 1 banner, phasing, VA status; no CDN libs
├── html/references.html             # glossary, Results data dictionary, sources with metadata links; no CDN libs
├── html/reference-hub.html          # v0.6 reference hub incl. data + model inventory (Calcite + AG Grid)
├── html/scoring-rubrics.html        # v0.4 interactive rubrics (score an asset, rubric tables, framework, decisions, departures)
├── html/workshop-punchlist.html     # Workshop 1 task list (dated table, decisions open, print maps); status edited in the page data
├── html/vulnerability-assessment-feedback.html      # Workshop 1 digital sticky notes, same fields as the paper template (Nov. 4, 2026): Name at the top of the panel (no agency, no email, nothing required to send), hazard stations, click an asset or drop a pin, Concern level (Greatest Concern, Somewhat Concerned, Just Adding a Note = 1 to 3 on the map), Issue description, missing flag; the card and map popup show the asset's draft class, score, the reason in plain words, and the exposure x wE + sensitivity x wS line (PAIR_W, reasonFor, mirrors vulnerability-assessment.html arcReason); "Flooding you have seen" draws polygons (when, what happened) sent to the flood areas v2 layer with the same Send, tagged with the send's id; sends are keyed by name + browser and "Next person" clears the browser, so staff can type up the paper notes one person at a time; CSV fallback; Report out + Flooded areas tabs, printable master list; the table drawer starts collapsed so the map keeps the pane
├── scripts/create_workshop_feedback_layer.py  # makes/checks the AGOL notes table and the flood areas v2 polygon layer (each with submit/read views made by manager.create_view, which sets isUpdatableView; the Oct. 30 flood areas service, owner amcclary_TRPA, has a non-updatable submit view that refuses every add and is left unused) for the feedback page (--smoke-test)
├── scripts/build_curated_gdb.py     # PROTECT_curated.gdb on F: (config `curated:`): only the hazard + asset layers and fields the assessment and pages use, NDOT rows excluded; DataDictionary + DatasetCatalog tables, CSV copies beside it
├── html/vulnerability-assessment.html                # the Vulnerability Assessment page: Overview + one tab per hazard (data-driven MODES config)
├── html/vulnerability-assessment-guide.html          # one-page printable guide to the Vulnerability Assessment page (Nov. 4, 2026: at-a-glance copy); QR codes for the Vulnerability Assessment and its Feedback page are static SVGs in html/img/qr/ from scripts/make_qr.py (no libraries; rerun if a URL changes)
├── html/criticality-assessment.html      # criticality app, Vulnerability Assessment page format (18,285 segments, adjustable weights; overall classes break at the 25th, 50th, and 90th percentiles by default, a switch returns to the Vulnerability Assessment page's quarters; reads data/processed/results/roads_geometry.geojson + roads_criticality.json)
├── html/criticality-qa.html         # UNLINKED by request (Nov. 2, 2026): reached only by its URL, so keep it out of every Pages menu, the index cards, and page copy. Criticality outlier review: open checks first (cards, map, grid), Oct. 30 fixes, by-design top-quarter note; reads data/processed/results/criticality_qa.json from scripts/criticality_qa.py (re-run after every criticality rebuild)
├── html/od-services-index.html      # OD access-to-services index (criticality factor 4); reads roads_od.json + roads_geometry.geojson (publish_results.py, clean street layer), no longer the PROTECT_VA service
├── html/baseline-assessment.html    # summary of ICF's draft Baseline Assessment (findings, proposed actions, roles); no CDN libs
├── html/historic-hazards.html       # v0.1 observed hazard record (CAL FIRE perimeters, USGS landslides, earthquakes)
├── html/climate-data.html           # v0.2 climate inputs page (sources, metrics, Atlas 14 DDF, decisions)
├── html/tahoe-precip-events.html    # storm events + debris-flow explorer (CDN libs, embedded culverts + WRF I1h grid)
├── html/_archive/                   # retired pages, not served by Pages (ARCHIVED.md lists why)
├── climate/                         # self-contained climate data pipeline (own config.yaml, src/, notebooks/)
├── debris-flow/                     # USGS wildcat debris-flow pipeline (own config.yaml, src/, notebooks/)
├── print-maps/                      # print maps from one Pro template layout (arcpy.mp): config.yaml holds the project, exports, NDOT guard, and the corridor x hazard sheets; print_maps.py inspect | check | export | build; build_layers.py sets up the Vulnerability Assessment page's layers, owned maps (the dark-basemap criticality map), and layouts in the project from PROTECT_curated.gdb per layers.yaml (keep it in step with vulnerability-assessment.html), creating what is missing and keeping what is there (--replace rebuilds); since Oct. 30 the maps are finished and exported by hand in Pro; the PDFs live on F: (PROTECT_analysis\Maps). Since Nov. 3 the working project is the local C:\GIS\PROTECT_local\PROTECT_Maps.aprx made by localize_aprx.py from the F: project: local copies of the curated, hazards, analysis, Assets, Hazards, data, and Cartography geodatabases, the SDE layers on maps.trpa.org services (four exported to PROTECT_reference.gdb), the jurisdiction culvert deliveries and the 9 GB USGS raster left on F:. The analysis gdb holds NDOT rows, so that folder stays outside the repo; *.aprx is gitignored. Nov. 4: resize_aprx.py makes PROTECT_Maps_24x36.aprx beside it (export writes every map and layout to .mapx/.pagx under PROTECT_Maps_files; build copies the project and resizes every layout with one uniform factor, map frame grown to the new page and refit to the same width of geography; Pro's own changePageSize scales text by the height ratio and boxes per axis, which breaks the legend). localize_sources.py (config.yaml local_sources:) pulls the network layers the print maps draw (NHDPlus HR, TRPA boundary, county, highways, streams and lakes) into PROTECT_reference.gdb clipped to the print extent and repoints a project's print maps at them; the Terrain hillshade stays on the image service by choice. At 24 x 36 the maps draw at 1.5 x the scale denominator, so the Transportation service's Corridors sublayer (on at 1:85,000 and smaller) would appear; apply turns that layer off. First result: PROTECT_Maps_24x36_local.aprx (apply --out, Nov. 4: 97 layers repointed, 36 sublayers converted, Transportation off in 12 maps); it also revived the template's County and Highway layers, whose merged SDE-plus-URL connection had drawn nothing since Nov. 3, so county lines and county and highway labels appear that the earlier local projects did not show
├── scripts/                         # analysis scripts and notebooks (incl. ra2ce/)
└── Hazard_Asset_Pairs.md            # plain-text source-of-record for pairs + framework
```

## Conventions

- **Dashboard stack**: single-file HTML, CDN libraries. Calcite Components (shell/tabs), AG Grid
  (tables), TRPA brand (Open Sans, TRPA Blue / Navy). Pair the `trpa-dashboard-stack` and
  `trpa-brand` skills. No build tools.
- **Criticality quarters use the Phosphor thermal ramp (Oct. 28, 2026):** `#042333`, `#6E4694`, `#F37D4D`, `#E8FA5B`
  (quarter 0 to 3; joshuastevens.net/phosphor control colors, OKLab, four even steps), `RAMP` on
  `criticality-assessment.html` and `CRIT_RAMP` on `vulnerability-assessment.html`, kept in step. Criticality maps draw on the
  `dark-gray-vector` basemap (the pale top quarter vanishes on light gray) with the boundary in TRPA Ice;
  `vulnerability-assessment.html` swaps basemaps per view (`setBase`). Bars and legend swatches get a thin dark edge.
- **Headers = navy / Dark Blue (`#003B71`), white text.** Standardize the page header bar and all
  table headers on navy: AG Grid (`--ag-header-background-color: var(--trpa-navy)`) and static tables
  (`table.ref`, `table.matrix`). TRPA Blue (`#0072CE`) is the accent against navy (the version chip,
  no header call-to-action buttons: Mason dropped the "Open Risk Index Tool" button Oct. 8) and for KPI card top-borders / links.
- **Page header treatment matches the `regional-plan-tracking` dashboard suite** (in the
  `data-visualization` repo): a single clean navy band, no accent stripe. Inside, a centered
  `.header-content` (max-width = the page's `main`) holds, left to right: the TRPA color logo
  (`html/trpa-logo-color.png`, the blue Lake Tahoe silhouette, 50-54px tall, links to `trpa.gov`),
  a `.header-text` block (`.agency` eyebrow + `h1` + `.header-sub` subtitle), and a right-aligned
  meta cluster (version chip, the Pages menu, page-specific links; no separate Home link, Home is
  the first item in Pages). Eyebrow and subtitle are TRPA Ice
  (`#B4CBE8`); the `h1` is white. The blue silhouette on navy is intentional - same as the suite.
  **Exception, `vulnerability-assessment.html` (Oct. 13, 2026):** one sticky navy band about 56 px tall holding the
  logo, title, hazard tabs, a Draft chip (the tab's banner text is its tooltip), a How to use button
  (native `<dialog>`), and Pages. The map fills the first screen; the tab's lead sits at the top
  of the map panel. The panel folds to a slim strip and resizes by dragging its edge (width and
  fold state kept in localStorage); its navy head shows the tab name and is shared with the
  full-screen floating panel. Culverts draw only at 1:120,000 and closer on Overview, Landslide,
  and Debris flow (`CULVERT_MIN_SCALE`); Flooding shows them at every scale. A culvert click draws
  its drainage area on every tab with culverts (`culvertDrainage`).
- **AG Grid pinned to 31.3.2.** The v33+ Theming API drops the legacy `ag-theme-quartz` CSS this page
  uses; do not bump without migrating theming. Grids created inside hidden Calcite tabs are re-fit
  (`sizeColumnsToFit`) only when visible (guard on width > 0) to avoid zero-width warnings.
- **AG Grid `cellRenderer` renders empty in this build** (string, DOM, and class forms all fail;
  A/B-tested). Color cells with `cellStyle`, format text with `valueFormatter`, and make links with
  `onCellClicked` - never `cellRenderer`. The `colorCell(map)` helper returns a `cellStyle` function.
- **CSV round-trip editing.** Every AG Grid and static data table has an Export CSV button - that is
  how Mason edits this data (export, edit in a spreadsheet, hand the CSV back to apply). Keep one on
  every new grid/table: AG Grids use `api.exportDataAsCsv`; static tables use the `tableToCsv` helper.
- **ArcGIS + UMD load order.** On any page that loads the ArcGIS Maps SDK alongside Plotly/AG Grid
  (e.g., `vulnerability-assessment.html`), load Plotly and AG Grid *before* the ArcGIS `<script>`. ArcGIS's
  Dojo/AMD loader otherwise makes those UMD bundles register as AMD modules (`Error: multipleDefine`;
  `window.Plotly` / `window.agGrid` end up undefined and the map fails). Pages without ArcGIS (the hub,
  the inventory) are unaffected.
- **Calcite components created after load do not register on ArcGIS pages.** The ArcGIS SDK 4.31 registers its own Calcite build for its widgets (button, icon, loader, scrim); a second Calcite include then never defines the rest, so `calcite-switch`, `calcite-block`, or a segmented control inserted by script after load stays an empty tag. Static Calcite markup present at parse time upgrades by luck of order. On `vulnerability-assessment.html` (Oct. 11, 2026) every page-owned control is native: `input.sw` switches, a `details.block` collapsible, `.cb` and `.btn` buttons. Do the same on any page that both loads the SDK and builds its panel in script.
- **`html/reference-hub.html` and `Hazard_Asset_Pairs.md` mirror the pair list.** When pairs change, update
  the grid's `pairs` array in the HTML and the markdown table. The 32-element data inventory lives in
  the HTML and `PROTECT_DataModel_Inventory.xlsx`, not in the markdown.
- **Punctuation**: no em-dashes (use a hyphen or colon), following the Reporting house style.
- **Copy register (all pages, revised Oct. 9, 2026)**: readers are workshop attendees first,
  the consultant and the data team second. Plain, direct, third person: everyday words in the
  page body ("drainage area", "cannot pass the 100-year storm", "which roads matter most"),
  with the methodology's terms in tooltips or collapsed blocks and glossed the first time they
  appear. Leads are two sentences at most, banners one, footers one line. Anything over about
  three sentences of method, framework, or sources goes into a collapsed
  `<calcite-block collapsible>` or a tooltip; nothing is deleted, every fact stays reachable.
  House style still applies: Oxford commas, "percent" and "to" not symbols, one to nine spelled
  out, abbreviated months with dates. Framework vocabulary, where it appears, follows the draft
  VA Methodology: "component 1, 2, 3", "vulnerability score" and "vulnerability class (High,
  Medium, Low)", "Vulnerability = (Exposure Score x wE) + (Sensitivity Score x wS)", "Tahoe
  Resilience Improvement Plan (TRIP)". When copy depends on something not in the repo, ask
  Mason rather than guess.
- **`html/scoring-rubrics.html` mirrors `docs/SCORING_RUBRICS.md`.** When a rubric changes, update
  the `PAIRS` and `DECISIONS` arrays in the HTML and the markdown together. Indicator values and
  scores are the consultant's Aug. 20 draft tables (half-point scale, the draft's breaks and
  directions); anything TRPA adds or changes is tagged TRPA proposal and numbered in the
  decisions. The page's departures table lists every such item.
- **Archiving a page**: `git mv` it into `html/_archive/`, add a row to `ARCHIVED.md` there, and
  remove its links and landing-page card. Do not delete history.
- **No staff names** in committed files. Neutral attribution ("the analyst", "the agency"); naming
  the orgs ("TRPA", "ICF") is fine.

## Local preview

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m http.server 8011 --directory html
# http://localhost:8011/
```

Or use the checked-in Claude Code preview config: `.claude/launch.json` (server name `protect`).
That server roots at `html/`, so the root home page and every menu's Home link need `protect-root`
(port 8012, repo root; pages at `/html/...`).
