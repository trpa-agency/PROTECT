# PROTECT Risk Index Tool Scoping, v0.1 (May 2026)

Markdown port of `PROTECT_RiskIndexTool_Scoping_v0.1.docx`, the scoping document cited by
the Reference Hub. Staff and vendor names replaced with roles per repo rules. This is the
historical v0.1 record; later decisions supersede parts of it (climate data is processed
in-house by the `climate/` pipeline, wildfire data was procured through RFP 260018, the
site consolidated to five pages, and the culvert layer is now compiled from six
jurisdiction deliveries).

## Executive summary

The Risk Index and Resilience Improvement Tool is the Task 3.3 deliverable, a single-page
web application that lets technical audiences explore the FHWA VAST-based risk index, the
underlying vulnerability assessment, and the prioritized resilience projects across the
Lake Tahoe Region's transportation network. Built on TRPA's standard dashboard stack
(Calcite + ArcGIS Maps SDK + Plotly.js + AG Grid), consuming data from a backend Python
ETL pipeline that assembles inputs from TRPA, the consultant team, and contracted modeling
deliverables into published feature services. MVP target was the Steering Committee
kickoff in Spring 2026, building toward the Workshop 1 release in November 2026.

## What the tool does

Visualizes the PROTECT Risk Index across the transportation network at road-segment and
parcel scale. Lets users decompose the index into its four sub-indices (Exposure,
Sensitivity, Asset Value, Adaptive Capacity) to see what drives risk at a location.
Surfaces vulnerability-assessment results including pinch points, priority zones, and
segments where redundancy fails. Catalogs the prioritized resilience projects with cost
estimates and BCA inputs. Provides a transparent methods page documenting data sources,
scaling decisions, and last-updated dates.

## What the tool does not do

Not an evacuation planning tool (PROTECT is not an evacuation plan per the Engagement
Plan). Not a real-time operational tool (TSMO Plan and ITS territory). Not a permitting or
project-tracking tool (EIP Project Tracker). Not a public comment portal (trpa.gov project
page and survey infrastructure).

## Success criteria

Steering Committee kickoff, working framework with at least two sub-indices populated from
existing TRPA data. Workshop 1 (Nov 2026), complete vulnerability assessment and Risk
Index v1 visible to roughly 30 technical partners. Workshop 2 (May 2027), resilience
projects layer added. Final RIP delivery (2027), polished public-facing version released
alongside the Resilience Improvement Plan.

## Functional scope

Single-page HTML application, persistent header, KPI summary row, filter controls, tabbed
content. Tabs are Map (default, ArcGIS MapView with risk symbology on segments and layer
toggles for the master index, each sub-index, VA outputs, and projects), Charts (risk
distribution histograms, jurisdiction and road-class breakdowns, sub-index correlations,
project pipeline), Data Table (AG Grid, every analyzed segment, sortable and
CSV-exportable), Methods (plain-language VAST explanation, scaling decisions, equity
multiplier application, data sources, change log), and About. Map interactions include
segment popups with sub-index breakdowns, a Calcite layer panel, basemap switching, and a
geographic filter that syncs map extent and table content.

## Data architecture

Two-repo convention separating data assembly from presentation. The backend pipeline
follows the standard TRPA data engineering structure (config.yaml, .env, src/io.py,
numbered notebooks, docs/METHODS.md) with four stages. Extract pulls base layers from SDE,
REST services (mobility redundancy outputs, FEMA NRI, HIFLD), CSVs (climate projections,
equity study), and contractor modeling deliverables as they arrive. Transform does spatial
joins to road-segment grain, min-max scaling per sub-index, the equity multiplier on
Sensitivity, and combines into the Master PROTECT Index; EPSG 26910 for analysis, Web
Mercator for publishing. QA covers spatial null rates, sub-index coverage, distribution
sanity checks, and year-over-year deltas into a reviewable qa_report.csv. Publish writes
to a TRPA SDE feature class, syncs to an AGOL hosted feature service, and exports a
GeoJSON snapshot as offline fallback.

## Tech stack

Frontend, Calcite Design System 5, ArcGIS Maps SDK for JavaScript 4.31, Plotly.js 2.35,
AG Grid Community, TRPA agency colors (#0072CE primary, #003B71 navy), Open Sans, no
frontend frameworks, hosted on GitHub Pages from the trpa-agency org. Backend,
arcgispro-py3 with pandas, geopandas, arcpy, pyyaml, python-dotenv; manual runs during
development, Task Scheduler for production refresh; secrets in a gitignored .env.

## Phasing

Phase 1, MVP for SC kickoff (mid-June 2026), repo scaffolding, frontend framework, two
demonstration sub-indices from existing data, methods draft. Phase 2 (Jul-Aug 2026),
consultant VA outputs, bridge and culvert condition, climate projection inputs, mobility
pinch-point analysis. Phase 3 (Sep 2026), contracted fire modeling, flood inundation and
scour, avalanche and landslide runout, Risk Index v1 frozen for QA. Phase 4 (Oct 2026),
full QA pass, completed methods page, performance and accessibility checks, PMT
walkthrough. Phase 5 (Spring 2027), resilience projects layer with cost and BCA inputs,
before-after risk-reduction toggle, optional public-facing variant.

## Risks

Late-arriving contractor modeling deliverables (mitigated by a data-agnostic framework
with swappable placeholders), methodology divergence with the consultant's VA (mitigated
by early framework lock-in), and equity-multiplier misapplication (multiplier versus
additive changes results meaningfully; locked and documented in Methods).
