# PROTECT

TRPA's repository for the **PROTECT** transportation resilience work (FHWA *Promoting Resilient
Operations for Transformative, Efficient, and Cost-saving Transportation* grant). This repo focuses
on **Task 3 (Resilience Improvement Plan)**, specifically the **Task 3.3 Interactive Risk Index
Mapping Tool** and the vulnerability assessment scoping behind it.

The risk index follows the **FHWA VAST framework**: four sub-indices (Exposure, Sensitivity, Asset
Value, and Adaptive Capacity, reverse-scored) combine into a Master PROTECT Index, weighted alongside
Criticality.

## What's in this repo

```
PROTECT/
├── data/                   # input data, intermediate files (empty for now)
├── docs/                   # methodology and build notes (empty for now)
├── html/
│   └── index.html          # Task 3 reference hub: pairs, data inventory, framework (Calcite + AG Grid)
├── scripts/                # ETL / analysis scripts (empty for now)
├── Hazard_Asset_Pairs.md   # plain-text source-of-record for the pairs + framework
├── CLAUDE.md               # project context for Claude
├── LICENSE
└── README.md
```

## The reference hub

[`html/index.html`](html/index.html) (v0.3) is a single-file page on the standard TRPA dashboard
stack (Calcite Components 5, AG Grid, Open Sans, TRPA Blue). Four tabs:

1. **Pair Matrix** - hazard-asset pairs tagged by impact type and advance status, with exposure and
   sensitivity inputs, plus an assets x hazards coverage grid. Quick search + CSV export.
2. **Data Inventory** - 32 data elements mapped to VAST components and TRPA acquisition status, plus
   a 17-row model/tool inventory and the composite-index architecture.
3. **Framework & Methods** - the FHWA VAST framework, sub-indices, sensitivity and criticality
   indicators by asset, assessment approaches, and the RA2CE vs. Volpe RDR tool comparison.
4. **Open Decisions** - decisions and action items from the scoping doc and the 5/20 VA sync.

[`Hazard_Asset_Pairs.md`](Hazard_Asset_Pairs.md) is the plain-text source-of-record for the pairs and
framework.

## Architecture note

The v0.1 tool scoping doc proposes a future two-repo split: `protect-risk-index` (Python ETL) and
`protect-risk-index-tool` (the HTML dashboard, published via GitHub Pages). For now this single
`PROTECT` repo serves as the working hub; the split will happen when the Phase 1 MVP build starts
(target mid-June 2026).

## Local preview

```powershell
# from the repo root - serves html/ at the root URL
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m http.server 8011 --directory html
# then open http://localhost:8011/
```

A Claude Code preview config is checked in at `.claude/launch.json` (server name `protect`).

## Live site

Hosting is not yet decided (GitHub Pages on `trpa-agency.github.io` vs. a `protect.laketahoeinfo.org`
subdomain). The tool is an internal review draft until at least Workshop 1; do not publish or commit
raw internal source documents.

## Sources

- 5/20/2026 ICF/TRPA VA deck (sensitivity & criticality approach)
- `PROTECT_DataModel_Inventory.xlsx`
- `PROTECT_RiskIndexTool_Scoping_v0.1.docx` (Task 3.3 tool scoping)
- `Vulnerability Assessment.docx` (earlier working notes)
