# PROTECT

TRPA's repository for the **PROTECT** transportation resilience risk tool
(Task 3.3 Risk Index & Resilience Improvement Tool). It scores transportation
assets against natural hazards as **Risk = Vulnerability &times; Criticality**,
starting from a confirmed list of hazard-asset pairs.

## What's in this repo

```
PROTECT/
├── data/                   # input data, intermediate files (empty for now)
├── docs/                   # methodology and build notes (empty for now)
├── html/
│   └── index.html          # Hazard x Asset Pair Matrix: interactive single-file page (Calcite + AG Grid)
├── scripts/                # ETL / analysis scripts (empty for now)
├── Hazard_Asset_Pairs.md   # source-of-record matrix doc (markdown)
├── CLAUDE.md               # project context for Claude
├── LICENSE
└── README.md
```

## The Hazard x Asset Pair Matrix

[`html/index.html`](html/index.html) is the interactive version of the matrix,
built on the standard TRPA dashboard stack:

- **Calcite Components 5.0** for the page shell and tabbed layout
- **AG Grid Community** for the sortable, filterable, exportable pair matrix
- **TRPA brand**: Open Sans, TRPA Blue / Navy, agency earth-tone palette

Four tabs:

1. **Pair Matrix** - the confirmed and TBD hazard-asset pairs, with vulnerability
   inputs, failure mechanisms, and notes. Quick search and CSV export.
2. **Vulnerability Approach** - the modeling layers behind each hazard.
3. **Criticality Scoring** - the network-universal inputs (mirrored from the
   Dutchess County RIP methodology, plus Tahoe-specific additions).
4. **Open Items** - decisions outstanding before the next sync.

[`Hazard_Asset_Pairs.md`](Hazard_Asset_Pairs.md) remains the plain-text
source-of-record for the same content.

## Local preview

```powershell
# from the repo root - serves html/ at the root URL
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m http.server 8011 --directory html
# then open http://localhost:8011/
```

A Claude Code preview config is checked in at `.claude/launch.json` (server
name `protect`).

## Live site

Intended to publish via GitHub Pages from **`main` branch / `/html`** (matching
the EIP and Reporting repos) once Pages is enabled:

> https://trpa-mason.github.io/PROTECT/

## Sources

- `PROTECT_DataModel_Inventory.xlsx`
- `Vulnerability Assessment.docx`

(TRPA / ICF vulnerability assessment working notes. v0.2 supersedes v0.1, the
32-row inventory matrix.)
