# PROTECT: Hazard x Asset Pairs & Risk Index (v0.8)

**Task 3.3 Interactive Risk Index Mapping Tool** (PROTECT Plan, Task 3 Resilience Improvement Plan)

Plain-text source-of-record for the hazard-asset pairs and modeling approach. The interactive
version (with the data and model inventory and full framework) is the
[reference hub](html/reference-hub.html); this file and the hub's pairs grid are kept in mirror.

Sources: ICF draft VA Methodology (Aug. 20, 2026; scoring rubrics and weights per pair), 6/25/2026
VA discussion deck (decided pairs, three-step approach), 5/20/2026 ICF/TRPA VA deck (sensitivity &
criticality approach), `PROTECT_RiskIndexTool_Scoping_v0.1.docx`.

> v0.8 (Oct. 7, 2026) aligns the pair table with the consultant's Aug. 20 draft VA Methodology.
> The draft's matrix is the same **15 Include-in-VA pairs** as v0.7, so no pair changes status.
> What changes: the exposure inputs and sensitivity indicators for each VA pair now follow the
> draft's scoring rubrics; per-pair exposure and sensitivity weights are recorded (section 3); the
> screening equation is written as the draft states it, a weighted sum of exposure and sensitivity,
> with criticality carried separately (section 1); and the draft's open options (debris-flow
> exposure option 1 or 2, culvert debris potential source, missing-data defaults) are logged in
> section 7. TRIP-discussion and proposed pairs are unchanged.
>
> v0.7 (Aug. 4, 2026) revises the 6/25 decision on three points: every flooding pair is now scored
> in the VA (FL-AT and FL-TC move in from TRIP discussion), avalanche on bridges moves out of the VA
> to TRIP discussion, and the marina pair (WF-M) is dropped, retiring marinas as an asset class.
> Counts go from 14 in the VA and 9 TRIP-discussion to **15 in the VA and 7 TRIP-discussion**, plus
> the 4 proposed pairs.
>
> v0.6 (Aug. 3, 2026) adds four **proposed** pairs for Steering Committee review: seiche and high
> lake level against roads and active transport. Seiche resolves an existing inconsistency (tracked
> as data and rated in the sensitivity matrix, but with no pair). Shallow groundwater is handled as a
> sensitivity attribute rather than a hazard. Also records lake stage as tailwater on FL-C and adds
> WRF to the exposure dataset evaluation.
>
> v0.5 (Aug. 3, 2026) adopts the decided pair matrix and three-step assessment approach from the
> June 25 VA discussion: 14 pairs scored in the VA, 9 pairs excluded from the VA but discussed in
> the TRIP; LS-C reinstated as its own pair (v0.4 had folded it into DF-C); DF-B and FL-TC added;
> the screening formula is Vulnerability = (Exposure + Sensitivity) x Criticality, replacing the
> four-sub-index VAST framing of v0.3-v0.4.

---

## 1. The three-step assessment approach

Adopted at the 6/25 VA discussion, building on FHWA VAST guidance, and detailed in the Aug. 20
draft VA Methodology:

1. **Criticality assessment** - *What are the critical assets in the region?* Scope: roads,
   bridges, active transport, transit centers. Road segments are scored on equity (households below
   poverty, limited English proficiency, zero-vehicle households, population with a disability,
   equally weighted), traffic (2024 estimated AADT), detour length (added travel distance when the
   segment is removed from the network), and access to critical locations (origin-destination
   analysis). Live in [`html/criticality-index.html`](html/criticality-index.html) (18,253 segments,
   adjustable weights). Bridges and culverts inherit their segment's score. Class 1 and Class 2
   trails wide enough for emergency vehicles are critical; all transit centers are critical.
2. **System-wide, indicator-based vulnerability assessment** - *Where are the greatest
   vulnerabilities?* Scope: the 15 Include-in-VA pairs below. Score exposure and sensitivity per
   asset (0-3), then **Vulnerability = (Exposure x wE) + (Sensitivity x wS)**, with the weights set
   per pair (section 3). Time horizons: historical, mid-century (2050), late-century (2080).
   Results are reported at the asset level (individual scores) and regionally (clusters of
   high-vulnerability assets), bucketed High / Medium / Low on an interactive map. The 6/25 deck
   wrote the rating as (Exposure + Sensitivity) x Criticality; the Aug. 20 draft scores
   vulnerability without the criticality multiplier and uses criticality (step 1) alongside
   vulnerability to pick scenario locations and TRIP priorities. See section 7.
3. **Scenario-based disruption analyses** - *How does the system react to an event? Where are the
   pinch points?* For locations with high criticality and/or high vulnerability from steps 1-2,
   define plausible scenarios (including compounding events such as wildfire followed by debris
   flow) and run RA2CE on the Overture street network: direct impacts, detour lengths, travel-time
   changes, blocked assets, access to key destinations (hospitals, shelters, isolated communities),
   populations impacted, cross-sector cascades, and (optionally) Expected Annual Loss from loss
   functions and value of time. Presented as case studies. Assets and hazards: TBD after screening.

Network redundancy and adaptive-capacity questions are handled in step 3, not as a separate
sub-index.

## 2. Hazard x Asset pairs (15 in the VA, 7 TRIP-discussion; plus 4 proposed)

Impact: **PC** = physical damage + cascading operational disruption; **OP** = operational only.
Status: **Include in VA** = scored in the risk-based vulnerability assessment;
**TRIP discussion** = excluded from the VA; impacts and potential strategies are discussed in the
Resilience Improvement Plan instead; **Proposed** = added after the 6/25 decision, not yet confirmed.

| ID | Hazard | Asset | Impact | Status | Exposure inputs | Sensitivity indicators | Notes |
|----|--------|-------|--------|--------|-----------------|------------------------|-------|
| AV-R | Avalanche | Roads | OP | Include in VA | Dominant slope angle within 1,000 ft (DEM or 2022 lidar) + historical avalanche record within 1,000 ft (Sierra Avalanche Center accident map, National Avalanche Accident Database) | None (exposure x 1.0) | Current terrain conditions only; 35-45 degrees with a record scores 3. Initial focus: Hwy 50, 89, 28, 207, 431; confirm scope with NDOT/Caltrans |
| AV-B | Avalanche | Bridges | PC | TRIP discussion | | | Moved out of the VA after 6/25: not being scored, impacts covered in the plan |
| DF-B | Debris Flow | Bridges | PC | Include in VA | Option 1: StreamStats mean basin slope + drainage area + contracted predicted soil burn severity. Option 2: Wildcat debris-flow likelihood + combined hazard class + soil burn severity | Span type (NBI 45), bridge condition (NBI 58-60), span length (NBI 48) | Added at the 6/25 VA review. Exposure option 1 or 2 undecided (section 7) |
| DF-C | Debris Flow | Culverts | PC | Include in VA | Same as DF-B (option 1 or 2) | Debris potential of the basin: StreamStats mean basin slope x majority NLCD landcover (option 1) or CULVERT tool WDBFM debris-flow score, 0-5 (option 2) | Split from landslide per 5/20. The purchased pre-fire severity surface makes this predictive rather than post-hoc, and is the primary Wildcat input |
| DF-R | Debris Flow | Roads | PC | Include in VA | Same as DF-B (option 1 or 2) | Pavement condition, paved vs. unpaved | Split from landslide per 5/20; July 14 event hindcast on the Storm Events page |
| FL-B | Flooding | Bridges | PC | Include in VA | NBI water adequacy (Item 71) + change in 100-yr flood depth vs. historical (contracted flood model, max of fluvial and pluvial) | Channel condition (NBI 61), scour criticality (NBI 113, 40 percent), span type (NBI 45), bridge condition (NBI 58-60) | Exposure 0.3 / sensitivity 0.7. Large culverts score with bridges. NBI fields from the FHWA National Bridge Inventory; 2022 lidar asset elevation optional to refine depth |
| FL-C | Flooding | Culverts | PC | Include in VA | 100-yr flood depth over the road (contracted flood model, max of fluvial and pluvial) | Debris potential of the basin (StreamStats slope x landcover, or CULVERT tool score) + 100-yr capacity loading ratio Qevent/Qdesign (StreamStats flows; Qdesign from asset data or the CULVERT tool) | Exposure 0.3 / sensitivity 0.7 (small culverts). TRPA culvert layer compiled (7,858 assets, 6 jurisdictions); CULVERT screening on the Storm Events page. High lake stage reduces outlet capacity independent of rainfall |
| FL-R | Flooding | Roads | PC | Include in VA | Floodplain extent, 10- to 1,000-yr (35 percent) + 100-yr flood depth (35 percent); contracted flood model, max of fluvial and pluvial | Pavement condition, paved vs. unpaved, truck AADT (10 percent each) | Lowland and valley segments most exposed. Defaults: fair, paved, truck AADT TBD |
| FL-AT | Flooding | Active Transport | PC | Include in VA | Same as FL-R | Paved vs. unpaved, trail slope (15 percent each) | Moved into the VA after 6/25: all flooding pairs are scored. Defaults: unpaved, slope TBD |
| FL-TC | Flooding | Transit Centers | PC | Include in VA | Same as FL-R, with lower depth thresholds (3 at more than 8 ft) | None (exposure x 1.0) | Added at the 6/25 VA review; moved into the VA so all flooding pairs are scored |
| LS-B | Landslide | Bridges | PC | Include in VA | USGS Landslide Susceptibility Index or recorded landslide (CA Landslides Database), 50 percent + Cal-Adapt annual precipitation change, 20 percent | Span type (NBI 45), bridge condition (NBI 58-60), span length (NBI 48) | Large culverts score with bridges |
| LS-C | Landslide | Culverts | PC | Include in VA | Same as LS-B | Culvert size (opening width), culvert condition if available | Post-fire compounding required per ICF |
| LS-R | Landslide | Roads | PC | Include in VA | Same as LS-B | Embankment condition or stabilization measures if available; otherwise pavement condition | Scored on susceptibility; runout modeling is not being pursued |
| WF-AT | Wildfire | Active Transport | PC | Include in VA | Contracted wildfire risk: burn probability (70 percent) + flame length (30 percent), max within a 300-ft buffer; current conditions | None (exposure x 1.0) | |
| WF-R | Wildfire | Roads | PC | Include in VA | Same as WF-AT | Wooden guardrails present (default: none) | Fire modeling is procured: burn probability, flame length, intensity classes, ember load, fire pathways, and firesheds. Crown fire potential available but not in the rubric |
| WF-TC | Wildfire | Transit Centers | PC | Include in VA | Same as WF-AT | None (exposure x 1.0) | |
| EQ-B | Earthquake | Bridges | PC | TRIP discussion | USGS Seismic Hazard Maps; ComCat; ShakeMaps | Seismic retrofit status, bridge condition, age | |
| EQ-R | Earthquake | Roads | PC | TRIP discussion | USGS Seismic Hazard Maps; ComCat; ShakeMaps | | |
| WD-R | Wind | Roads | OP | TRIP discussion | gridMET wind (Climate Engine); ASCE 7 | Operational: tree blow-down, power-line breaks | |
| WS-AT | Winter Storm | Active Transport | OP | TRIP discussion | | | |
| WS-R | Winter Storm | Roads | OP | TRIP discussion | SNODAS SWE; Cal-Adapt snow projections; NRI Winter Storm | Operational: extended closure, plow-depot overrun, ITS power loss | |
| WS-TC | Winter Storm | Transit Centers | OP | TRIP discussion | | | |
| SE-R | Seiche | Roads | PC | **Proposed** | TRPA bathymetry + wind models; USGS seismic (seismically triggered seiche) | Road elevation above lake stage, shoreline armoring, pavement foundation | Shoreline routes: Hwy 28 and US-50 East Shore |
| SE-AT | Seiche | Active Transport | PC | **Proposed** | TRPA bathymetry + wind models | Elevation above lake stage, paved vs. unpaved | East Shore Trail and shoreline bike paths |
| LL-R | High Lake Level | Roads | PC | **Proposed** | TRPA Lake Tahoe at High Water (live); lake stage exceedance frequency | Road elevation, pavement foundation, depth to groundwater | Data live today; lake stage is regulated, so exceedance frequency is tractable |
| LL-AT | High Lake Level | Active Transport | PC | **Proposed** | TRPA Lake Tahoe at High Water (live) | Elevation above lake stage | Shoreline paths inundate at sustained high stand |

**Proposed** = added after the June 25 decision, pending Steering Committee confirmation. Seiche was
already tracked as a data element and rated in the asset and vulnerability matrix but had no pair,
which is the inconsistency these entries resolve. High lake level also acts as **tailwater at
shoreline culvert outlets**, reducing capacity independent of rainfall; that is carried as an
exposure input on FL-C rather than a separate culvert pair.

**Marinas are retired as an asset class.** The wildfire-marina pair (WF-M) was the only pair that
used them, and it is dropped. Marinas are privately owned, which made both criticality scoring and
an agency response pathway awkward, and no other pair depended on the class.

**Shallow groundwater is deliberately not a hazard.** It is a persistent site condition with no
event frequency, so it enters as a *sensitivity* attribute (depth to groundwater on roads and
culverts, alongside pavement foundation) rather than a pair. If groundwater rise under climate
change is modeled later, that becomes an exposure input beside Climate: Subsidence.

## 3. Scoring weights and indicators (Aug. 20 draft VA Methodology)

Every indicator scores 0-3 and carries a weight; exposure and sensitivity weights sum to 1.0 per
pair. Defaults for missing data are noted in the table above where the draft sets them; most are
still "TBD" in the draft (section 7).

| Hazard | Roads | Bridges and large culverts | Small culverts | Active transport | Transit centers |
|--------|-------|----------------------------|----------------|------------------|-----------------|
| Flooding | E 0.7 / S 0.3 | E 0.3 / S 0.7 | E 0.3 / S 0.7 | E 0.7 / S 0.3 | E 1.0 |
| Landslide | E 0.7 / S 0.3 | E 0.7 / S 0.3 | E 0.7 / S 0.3 | not scored | not scored |
| Wildfire | E 0.7 / S 0.3 | not scored | not scored | E 1.0 | E 1.0 |
| Debris flow | E 0.7 / S 0.3 | E 0.7 / S 0.3 | E 0.7 / S 0.3 | not scored | not scored |
| Avalanche | E 1.0 | not scored | not scored | not scored | not scored |

Bridges and culverts flip to sensitivity-heavy under flooding because scour, channel condition,
and capacity loading drive failure more than inundation depth does. The draft scores large culverts
with bridges (NBI fields) and small culverts on their own rubric (debris potential and capacity
loading ratio).

Exposure datasets by hazard: flooding from the contracted flood model (max of fluvial and pluvial
depth; SSP2-4.5 and SSP5-8.5; 5- to 1,000-yr events; 2020, 2030, 2050, 2100); landslide from the
USGS Landslide Susceptibility Index, the California Landslides Database, and Cal-Adapt annual
precipitation projections (RCP4.5/SSP2-4.5 and RCP8.5/SSP5-8.5; 2050, 2080); wildfire from the
contracted fire-behavior package (burn probability from FSim, flame length from WildEST; current
conditions only); debris flow from StreamStats and the contracted soil burn severity surface
(option 1) or the USGS Wildcat pipeline in `debris-flow/` (option 2); avalanche from DEM or 2022
lidar slope plus avalanche accident records.

Condition sources: **bridges** from the FHWA National Bridge Inventory (public annual dataset, no
agency request needed); **culverts** from the compiled TRPA layer and condition table (7,858
assets, six jurisdictions); **pavement** is TBD, with jurisdiction outreach planned - the
remaining sensitivity gap for the road pairs. The TRPA Equity Study (vulnerable populations)
enters through criticality (step 1), not as a vulnerability multiplier.

## 4. Schedule (6/25 deck)

Jul 2026 asset data updates + criticality assessment; Aug data acquisition, screening, and the
**first Steering Committee**; Sep scenarios + start tool build; Nov workshop vets draft results +
tool; Dec finalize VA results and tool. Nothing scheduled in October.

## 5. Disruption-risk tool: RA2CE selected

**RA2CE** (Deltares) is the selected disruption-risk engine (Aug 2026), running on the
Overture-derived street network; analysis work lives in `scripts/ra2ce`. **Volpe RDR** was evaluated
and not pursued (retained as a reference for Task 3.4 BCA framing). Key RA2CE inputs: network
geometry and attributes, hazard rasters by scenario / return period, vulnerability / damage
functions, link-failure rules, and optional economic inputs (replacement cost, value of time,
EAD/EAL).

## 6. Data inventory

32 data elements, each mapped to the assessment step it feeds (Step 1 Criticality, Step 2 Exposure,
Step 2 Sensitivity, Step 3 Disruption, or Context / TRIP for elements that support the plan or Task
3.4 rather than the scoring), plus the model/tool inventory, are catalogued in the **Data and Model
Inventory** tab of the [reference hub](html/reference-hub.html) (the source of record) and
`PROTECT_DataModel_Inventory.xlsx`. Not reproduced here to avoid divergence.

## 7. Open decisions

**Vendor risk scores versus this screening.** Both contracted datasets ship a pre-computed risk
score: an average-annual-loss measure for flood and a net-value-change measure for wildfire. Each is
structurally a combination of exposure, sensitivity, and asset value, the same shape as this
screening read against criticality. Recommendation: take the
component layers as exposure and sensitivity inputs, score them through the screening with TRPA
criticality, and keep the vendor scores as validation cross-checks. Using them directly would rank
flood by average annual loss, wildfire by a federal valued-resource framework, and everything else by
TRPA criticality, leaving the pairs incomparable. The wildfire package also models critical access
roads, overlapping the Criticality Index.

**Contracted flood licence expires July 2027**, roughly two months after the final plan. The wildfire
package is perpetual. Establish the renewal cost, whether derived scores survive expiry (a licensing
question), and whether flood should be architected so the contracted model is swappable back to FEMA,
StreamStats, and HEC-RAS without a rebuild.

**Scenario mismatch.** The contracted flood data offers SSP1-2.6, SSP2-4.5, and SSP5-8.5; this
pipeline runs SSP2-4.5 and SSP3-7.0. Only SSP2-4.5 overlaps, which forces the headline-scenario
decision (climate page, decision 1). Horizons differ too: snapshot years 2030 / 2050 / 2100 against
30-year climatologies, where 2050 maps onto 2040-2069 but 2100 does not map onto 2070-2099.

**Do not double-count the climate adjustment.** The contracted flood model already applies Atlas 14
curves and delivers climate-adjusted depths; scaling Atlas 14 again by LOCA2 change factors would
apply the adjustment twice for flood.

**Fuelscape consistency.** The contracted fire-behavior runs need a fuelscape, and a separate 2026
fuels package is also being delivered. Confirm both run on the same fuelscape or document the
discrepancy, or treated areas will differ between products.

**How pair scores aggregate to an asset-level rating.** One asset appears in several pairs: a
culvert carries FL-C, DF-C, and LS-C; a bridge carries FL-B, DF-B, LS-B, and AV-B. Whether the
asset's rating is the highest pair, the sum, or a weighted combination is not decided. Summing
risks double-counting what is physically one failure mode at a location.

Landslide and debris flow stay separate hazards (confirmed Aug. 3, 2026). Their triggers differ:
landslides are multi-day saturation failures scored against static geology and slope, while debris
flows are burst-driven and fire-conditioned, with a 15-minute intensity threshold and a burn-severity
exposure surface. Merging them would force one rainfall metric and lose that resolution. The split
makes the aggregation rule above matter more, not less.

**Criticality in the rating (Aug. 20 draft).** The draft scores vulnerability as a weighted sum of
exposure and sensitivity and keeps criticality as a separate component used to select scenario
locations and TRIP priorities. The 6/25 deck multiplied by criticality. Confirm with the consultant
which form the tool's headline rating uses; the tool can show both, but the map legend needs one.

**Debris-flow exposure option.** Option 1 (StreamStats slope and drainage area plus predicted soil
burn severity) or option 2 (Wildcat likelihood and combined hazard class plus soil burn severity).
The draft's bridge and culvert sections read "same as roads, pull in once we decide on option 1 or
2." The `debris-flow/` Wildcat pipeline supports option 2; option 1 needs StreamStats basin
delineation at every asset.

**Culvert debris potential and design capacity.** Debris potential comes from StreamStats slope
and landcover (option 1) or the CULVERT tool WDBFM score (option 2). The capacity loading ratio
needs Qdesign, which is missing for most culverts; the CULVERT tool can estimate it. The design
event for the ratio is undecided (100-yr likely, above the design standard of most culverts).

**Missing-data defaults.** The draft leaves most defaults "TBD": truck AADT, NBI water adequacy,
channel condition, scour criticality, span type, bridge condition, span length, culvert size and
condition, trail slope, basin slope, and landcover. Set each one or the scoring will silently drop
assets. Set defaults so far: pavement condition fair, roads paved, trails unpaved, no wooden
guardrails.

Other headline items: scenario definitions, assets, and hazards for step 3 (after screening),
analysis grain (segment vs. parcel), climate-data sourcing for commercial flood data (TRPA
purchase vs. add to ICF contract), data hand-off contract, hosting domain, and public visibility.
Climate-specific decisions live on the [climate data page](html/climate-data.html) Open Decisions
tab.
