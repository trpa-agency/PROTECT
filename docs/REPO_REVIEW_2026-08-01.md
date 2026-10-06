# PROTECT Repo Review, August 2026

Full audit of the working copy as of 2026-08-01, covering the climate pipeline, the culvert layer engineering, the published HTML pages, and repo level hygiene. Four independent review passes were run (one per area) and merged here. Findings are ranked by priority. Each item names the file, what was found, and the suggested fix. Items marked "decision needed" require a call from the data team or partners before anyone acts.

Reviewed against the repo's own standards where they exist, including docs/SESSION_NOTES.md, climate/docs/METHODS.md, the trpa-data-engineering conventions, and the constraint that this repo is public and served by GitHub Pages.

---

## Priority 1. Fix before the next push

These involve the public visibility of the repo or data agreements.

### 1.1 data/vendors.csv should leave the repo entirely

`data/vendors.csv` is the RFP vendor research list, roughly 50 commercial vendors with notes and price points, including specific price points for flood data. The repo's own rule (SESSION_NOTES.md header) is no commercial vendor names in committed files, since GitHub Pages serves this publicly. This file breaks that rule about 50 times over and also exposes procurement research.

Fix. Move the file out of the repo (a OneDrive or Teams location is fine), add `data/vendors.csv` to .gitignore, and check whether it was ever pushed. If it went to the public remote, the safe assumption is that the vendor list is public and a history rewrite (`git filter-repo`) plus force push is warranted. Run `git log --oneline --all -- data/vendors.csv` in the real clone to confirm.

Decision needed on whether to rewrite history or accept prior exposure.

### 1.2 Staff first name appears five times in data-model-inventory.html

`html/data-model-inventory.html` names "Andy" five times in task and status notes. The repo rule is no staff names in committed files.

Fix. Replace with a role ("GIS analyst") or remove. Search the other pages for first names while at it; the review found no others but the check is cheap.

### 1.3 Vendor name in reference-hub.html

`html/reference-hub.html` names the commercial vendor Xyloplan. Same rule as 1.1.

Fix. Replace with a generic description ("commercial fire modeling vendor") or remove the row.

### 1.4 The same flood price point also lives in docs/Hazard_Asset_Pairs.md

The same flood data price point from vendors.csv appears in `docs/Hazard_Asset_Pairs.md`. Fix alongside 1.1 so the number does not survive in a second location.

### 1.5 docs/index-copy.txt contains internal consultant coordination notes

`docs/index-copy.txt` reads as pasted internal notes about ICF coordination, including framing about what to hold back and ask for. Not appropriate for a public repo, and it appears to be a scratch copy rather than a deliverable.

Fix. Delete it. If the content matters, it belongs in Teams or the private project folder.

### 1.6 Verify what git actually tracks

The staged review copy cannot see git history. In the real clone run

    git ls-files | sort > tracked.txt
    git log --diff-filter=A --name-only --format= | sort -u > ever_added.txt

and check both lists against the sensitive items above plus `data/`, `outputs/`, and `logs/` (all meant to be gitignored). "html/index - backup.html" is currently unignored and looks tracked; either delete it or add it to .gitignore.

---

## Priority 2. Correctness issues in the pipelines

### 2.1 climate/config.yaml analysis.metrics is decorative

The documented consultant workflow is that ICF edits `climate/config.yaml` and the pipeline reruns. But notebook `05_transform` hardcodes its metric list and never reads `analysis.metrics` from config. A consultant edit to the metrics block would silently do nothing, which breaks the core promise of the placeholder-spec design.

Fix. Have 05_transform build its metric list from config.yaml, or if hardcoding is intentional for now, say so in a comment in both the config and the notebook so nobody is misled.

### 2.2 06_qa unit check caps at 12 files

The QA notebook's unit sanity check iterates only the first 12 stores rather than all 57 LOCA2 plus 26 WRF files. A unit or scaling problem in file 13 onward passes QA silently.

Fix. Drop the cap, or sample deterministically across every model and scenario combination rather than taking the head of the list.

### 2.3 README and METHODS still say LOCA2-Hybrid is 3 km

SESSION_NOTES.md records the correction (LOCA2-Hybrid is 6 km CA-only, disabled as redundant) but `climate/README.md` and `climate/docs/METHODS.md` still carry the 3 km claim. The climate-data.html methods tab has the same stale wording.

Fix. Sweep all three for "3 km" and align with SESSION_NOTES.

### 2.4 Legacy culvert gap fill can create duplicate assets

The 1,626 "TRPA Legacy (provisional)" adds were matched against jurisdiction culverts using a 25 m radius, but for line features the match used midpoints. A long culvert or ditch line whose midpoint sits more than 25 m from the legacy point defeats the match, and the legacy point is added even though the asset already exists. Given 1,626 provisional adds, even a few percent duplication is dozens of phantom assets feeding the risk screening.

Fix. Rerun the match using nearest distance to the line geometry, not the midpoint. Flag any legacy point within 25 m of a line feature (by geometry) that was still added, and review those by hand.

### 2.5 Caltrans SYSNO join keys pass through as floats

Caltrans source IDs were read as floats, so culvert_id values look like "caltrans|1234.0". This works today because both sides float-ified identically, but it will silently break the first time a re-delivery arrives as text or int.

Fix. Cast SYSNO to Int64 then string at ingest, and rebuild the ids.

### 2.6 Matched legacy condition records were dropped

When a legacy point matched an existing jurisdiction culvert, the legacy point was discarded along with any condition history attached to it. Condition records are the scarcest data in the layer; discarding them loses signal.

Fix. On match, re-parent the legacy condition records onto the surviving culvert_id instead of dropping them.

### 2.7 The Placer clip removed 28 percent of their delivery without documentation

Placer County's delivery extends outside the basin and the clip to the TRPA boundary dropped about 28 percent of their records. Correct behavior, but METHODS_culverts.md does not record it, and Placer may reasonably ask where their records went.

Fix. Add per-jurisdiction delivered versus retained counts to METHODS_culverts.md.

---

## Priority 3. Consistency issues in the HTML pages

### 3.1 tahoe-precip-events.html bypasses the projections review gate

The repo's publish gate says a human reviews projections output before it lands in a page. The precip events page embeds WRF-derived projection multipliers directly with no marker or review step. It was built in an assistant session, which is exactly the path the gate exists to check.

Fix. Either run its embedded numbers through the same review step and note the review date in the Methods tab, or add a visible "provisional, pending review" banner until that happens. Decision needed on which.

### 3.2 WRF resolution stated inconsistently

The precip events page says 3 km in one place while SESSION_NOTES records d02 at 9 km, and the derived-vars store is 3 km d03. Both statements are true of different stores, but the page does not say which it used.

Fix. State the store and domain explicitly wherever a resolution is quoted.

### 3.3 Stale hazard-asset pair IDs

The precip events page uses pair IDs FL-01, LS-01, LS-02 while docs/Hazard_Asset_Pairs.md now uses FL-C, FL-R, LS-R, LS-C. Fix the page to match the doc.

### 3.4 The embedded culvert inventory is now public

tahoe-precip-events.html embeds all 7,858 culvert points with attributes. The layer was engineered to be NDOT-free, so this appears permitted, but the decision to publish the full inventory on a public page was never made explicitly, and jurisdiction sharing terms vary.

Decision needed. Confirm each jurisdiction's delivery terms allow public web publication before the page goes to GitHub Pages, or swap the embedded layer for the maps.trpa.org service so access control lives server-side.

### 3.5 The precip events page is orphaned and heavy

No other page links to tahoe-precip-events.html, and it weighs 9.8 MB because Plotly and AG Grid are inlined (a workaround for a CDN failure on one machine). Fine for now; before wide sharing, consider restoring CDN loads with an integrity fallback and adding it to the hub page nav.

### 3.6 Two climate-data.html versions exist

The version in the repo and the version delivered to the Projects folder have diverged. Pick the repo copy as canonical, port anything missing, and delete or clearly mark the other.

---

## Priority 4. Hygiene

- climate/README.md is a full version behind the pipeline (missing WRF notebook 02 auto-detection, Atlas 14 pull, and the validation run). Refresh it.
- CLAUDE.md contains staff first names. Same fix as 1.2. It is likely untracked, but verify with git ls-files.
- Notebook numbering has a gap (no 04 in climate/notebooks). Either renumber or add a README line explaining the hole so the convention reads as intentional.
- outputs/manifest.csv concurrency rule (SESSION_NOTES process rule 4) is not stated in the notebooks themselves. Add a one-line warning comment at the top of each extract notebook.
- data/processed is gitignored but referenced by path in culvert_layer_engineering.ipynb with a hardcoded C:\ path. Move the path to a config cell at the top so reruns on another machine fail loudly in one place.

---

## What was checked and found sound

The LOCA2 pull manifest reconciles with the 57 stores listed in SESSION_NOTES. The WRF layout auto-detection in notebook 02 correctly handles both store layouts including the MPI member fallback. The FGOALS-g3 wind exclusion is applied consistently in the ensemble. Atlas 14 depths in the pages match the PFDS pulls. The .gitignore correctly excludes data/raw, outputs, and logs directories. The culvert QA notebook's relationship class checks pass and the CSLT epoch-ms bound check is in place. The burst catalog thresholds match the Atlas 14 Meyers 60-min PDS depths, and the frequency numbers quoted on the precip events page match the catalog JSON. The dataviz palette (ssp245 #0072CE, ssp370 #C45C1A) passes the skill's validator.

---

## Suggested order of work

First the public-exposure items (1.1 through 1.6) since every push widens exposure. Then the two pipeline correctness items with downstream effect (2.1 config metrics, 2.4 legacy duplicates). Then the page consistency sweep (3.1 through 3.3), which is quick. The decision-needed items (history rewrite, culvert publication terms, projections gate treatment for the events page) can move in parallel since they are conversations, not code.
