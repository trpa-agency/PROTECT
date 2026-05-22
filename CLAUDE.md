# CLAUDE.md - PROTECT

Project-specific overlay on `Documents\GitHub\CLAUDE.md`. Slim by design.

## What this repo does

Home for **PROTECT** Task 3 work. PROTECT = FHWA *Promoting Resilient Operations for Transformative,
Efficient, and Cost-saving Transportation* grant. Task 3 = Resilience Improvement Plan; 3.2 =
Risk-Based Vulnerability Assessment; **3.3 = Interactive Risk Index Mapping Tool** (this repo's
deliverable).

The risk index uses the **FHWA VAST framework**: sub-indices Exposure, Sensitivity, Asset Value, and
Adaptive Capacity (reverse-scored) combine into a Master PROTECT Index, weighted alongside Criticality
(Sensitivity ~10-20%, Criticality ~30%). Current artifacts: a reference hub (`html/index.html`, v0.3)
with tabs for the hazard-asset pairs, data inventory, framework/methods (incl. a hazard impact &
sensitivity matrix), and open decisions; a data-readiness tracker (`html/data-model-inventory.html`)
mapping each layer to its TRPA REST endpoint; and the **Phase 1 MVP map tool**
(`html/risk-index-tool.html`) - a map-centric SPA on live TRPA layers.

## Project context

- **Tool vision** (per `PROTECT_RiskIndexTool_Scoping_v0.1.docx`): a map-centric single-page app
  (Map / Charts / Table / Methods / About). Phasing: Phase 1 MVP ~mid-June 2026 (SC kickoff),
  Workshop 1 Nov 2026, Workshop 2 May 2027, final RIP 2027.
- **Two-repo future**: the scoping doc proposes `protect-risk-index` (Python ETL) +
  `protect-risk-index-tool` (frontend, GitHub Pages). Neither exists yet; this single `PROTECT` repo
  is the working hub until the MVP build starts.
- **Disruption-risk tool decision**: RA2CE (Deltares) vs. Volpe RDR (USDOT). ICF preparing pros/cons
  + level of effort; TRPA reviewing. Open.
- **Partners**: ICF is the consultant (climate resilience); TRPA Science & Data + Transportation
  teams lead. Next ICF/TRPA sync: June 3, 2026. Andy (TRPA) is exploring use cases and scripting with
  the Volpe RDR and RA2CE disruption-risk models, and built a street network from Overture data (the
  base network for those models).
- **MVP build**: the MVP Risk Index Tool is built in this repo's `html/` folder using the TRPA
  dashboard stack (Calcite + ArcGIS Maps SDK + Plotly + AG Grid).
- **Hosting / visibility**: GitHub Pages for now (`trpa-agency.github.io/PROTECT`); final home is
  `data.trpa.gov/PROTECT`. Internal review draft only - do NOT commit raw internal source docs
  (xlsx/docx/pptx) or publish broadly yet.

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
- **External (non-TRPA):** FEMA NRI, HIFLD, Cal-Adapt, Climate Engine, USGS StreamStats, RAMMS
  (sole-source). Competitive commercial data vendors (mobility, fire, flood, climate, geohazard, asset
  condition, multi-peril cat) are NOT named on the public pages - the researched landscape + outreach
  candidates live in `data/vendors.csv` (gitignored) and the project memory (`reference_data_vendors`).
  Keep only open-source / public / sole-source tools in the HTML; do not enumerate commercial vendor
  names in committed files.

The live readiness tracker is `html/data-model-inventory.html`.

## Where things live

```
PROTECT/
├── data/                            # input data, intermediate files (empty for now)
├── docs/                            # methodology and build notes (empty for now)
├── html/index.html                  # v0.3 reference hub (Calcite + AG Grid, TRPA brand)
├── html/data-model-inventory.html   # data + model inventory with REST endpoint tracking
├── html/risk-index-tool.html        # Phase 1 MVP map tool (Calcite + ArcGIS SDK + Plotly + AG Grid)
├── scripts/                         # ETL / analysis scripts (empty for now)
└── Hazard_Asset_Pairs.md            # plain-text source-of-record for pairs + framework
```

## Conventions

- **Dashboard stack**: single-file HTML, CDN libraries. Calcite Components (shell/tabs), AG Grid
  (tables), TRPA brand (Open Sans, TRPA Blue / Navy). Pair the `trpa-dashboard-stack` and
  `trpa-brand` skills. No build tools.
- **Headers = navy / Dark Blue (`#003B71`), white text.** Standardize the page header bar and all
  table headers on navy: AG Grid (`--ag-header-background-color: var(--trpa-navy)`) and static tables
  (`table.ref`, `table.matrix`). TRPA Blue (`#0072CE`) is the accent against navy (the version chip,
  the "Open Risk Index Tool" button) and for KPI card top-borders / links.
- **Page header treatment matches the `regional-plan-tracking` dashboard suite** (in the
  `data-visualization` repo): a single clean navy band, no accent stripe. Inside, a centered
  `.header-content` (max-width = the page's `main`) holds, left to right: the TRPA color logo
  (`html/trpa-logo-color.png`, the blue Lake Tahoe silhouette, 50-54px tall, links to `trpa.gov`),
  a `.header-text` block (`.agency` eyebrow + `h1` + `.header-sub` subtitle), and a right-aligned
  meta cluster (version chip / nav links / MVP badge). Eyebrow and subtitle are TRPA Ice
  (`#B4CBE8`); the `h1` is white. The blue silhouette on navy is intentional - same as the suite.
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
  (e.g., `risk-index-tool.html`), load Plotly and AG Grid *before* the ArcGIS `<script>`. ArcGIS's
  Dojo/AMD loader otherwise makes those UMD bundles register as AMD modules (`Error: multipleDefine`;
  `window.Plotly` / `window.agGrid` end up undefined and the map fails). Pages without ArcGIS (the hub,
  the inventory) are unaffected.
- **`html/index.html` and `Hazard_Asset_Pairs.md` mirror the pair list.** When pairs change, update
  the grid's `pairs` array in the HTML and the markdown table. The 33-element data inventory (32 from
  the workbook + WEPP) lives in the HTML and `PROTECT_DataModel_Inventory.xlsx`, not in the markdown.
- **Punctuation**: no em-dashes (use a hyphen or colon), following the Reporting house style.
- **No staff names** in committed files. Neutral attribution ("the analyst", "the agency"); naming
  the orgs ("TRPA", "ICF") is fine.

## Local preview

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m http.server 8011 --directory html
# http://localhost:8011/
```

Or use the checked-in Claude Code preview config: `.claude/launch.json` (server name `protect`).
