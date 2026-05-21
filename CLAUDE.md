# CLAUDE.md - PROTECT

Project-specific overlay on `Documents\GitHub\CLAUDE.md`. Slim by design.

## What this repo does

Holds the **PROTECT** transportation resilience risk tool (Task 3.3 Risk Index
& Resilience Improvement Tool). The current artifact is the Hazard x Asset Pair
Matrix: a confirmed list of hazard-asset pairs scored as
**Risk = Vulnerability x Criticality**, where vulnerability is hazard-specific
and criticality is network-universal.

Project / program context: pending - confirm the funding program and PROTECT
acronym expansion with Mason, then record it here.

## Where things live

```
PROTECT/
├── data/                   # input data, intermediate files (empty for now)
├── docs/                   # methodology and build notes (empty for now)
├── html/index.html         # interactive matrix (Calcite + AG Grid, TRPA brand)
├── scripts/                # ETL / analysis scripts (empty for now)
└── Hazard_Asset_Pairs.md   # plain-text source-of-record for the matrix content
```

## Conventions

- **Dashboard stack**: single-file HTML, libraries from CDN. Calcite Components
  for the shell/tabs, AG Grid for data tables, TRPA brand (Open Sans, TRPA Blue
  / Navy). Pair the `trpa-dashboard-stack` and `trpa-brand` skills. No build
  tools, no bundlers.
- **AG Grid is pinned to 31.3.2.** The v33+ Theming API drops the legacy
  `ag-theme-quartz` CSS this page uses; do not bump without migrating theming.
- **`Hazard_Asset_Pairs.md` and `html/index.html` carry the same content.**
  When the pair list changes, update both (the grid's `pairs` array in the
  HTML and the markdown table).
- **Punctuation**: this repo currently avoids em-dashes (use a hyphen or colon),
  following the Reporting house style. Confirm with Mason whether to keep this
  repo-wide.
- **No staff names** in committed files (dashboards, docs, commits). Use neutral
  attribution ("the analyst", "the agency"); "TRPA / ICF" for the consultant
  working notes is fine.

## Local preview

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m http.server 8011 --directory html
# http://localhost:8011/
```

Or use the checked-in Claude Code preview config: `.claude/launch.json` (server
name `protect`).
