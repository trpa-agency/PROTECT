# PROTECT: Hazard x Asset Pairs & Risk Index (v0.6)

**Task 3.3 Interactive Risk Index Mapping Tool** (PROTECT Plan, Task 3 Resilience Improvement Plan)

Plain-text source-of-record for the hazard-asset pairs and modeling approach. The interactive
version (with the data and model inventory and full framework) is the
[reference hub](html/reference-hub.html); this file and the hub's pairs grid are kept in mirror.

Sources: 6/25/2026 VA discussion deck (decided pairs, three-step approach), 5/20/2026 ICF/TRPA VA
deck (sensitivity & criticality approach), `PROTECT_RiskIndexTool_Scoping_v0.1.docx`.

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

Adopted at the 6/25 VA discussion, building on FHWA VAST guidance:

1. **Criticality assessment** - *What are the critical assets in the region?* Scope: roads,
   bridges, trails, transit centers. Indicators: evacuation route, detour length, AADT, proximity
   to strategic community assets, community priority zones. Live in
   [`html/criticality-index.html`](html/criticality-index.html) (18,253 segments, adjustable weights);
   bridges and culverts inherit their segment's score.
2. **System-wide, indicator-based screening** - *Where are the greatest vulnerabilities?* Scope:
   the 14 Include-in-VA pairs below. Score exposure and sensitivity per asset (0-3), then:
   **Vulnerability Rating = (Exposure + Sensitivity) x Criticality**, bucketed High / Medium / Low,
   delivered on an interactive map.
3. **Scenario-based disruption analyses** - *How does the system react to an event? Where are the
   pinch points?* For high-risk hazards and locations from steps 1-2, define 2-3 plausible
   scenarios per hazard and run RA2CE on the Overture street network: detour lengths, travel-time
   changes, blocked assets, degraded network performance, populations impacted, and (optionally)
   Expected Annual Loss from loss functions and value of time.

Network redundancy and adaptive-capacity questions are handled in step 3, not as a separate
sub-index.

## 2. Hazard x Asset pairs (6/25 decided: 14 in the VA, 9 TRIP-discussion; plus 4 proposed)

Impact: **PC** = physical damage + cascading operational disruption; **OP** = operational only.
Status: **Include in VA** = scored in the risk-based vulnerability assessment;
**TRIP discussion** = excluded from the VA; impacts and potential strategies are discussed in the
Resilience Improvement Plan instead; **Proposed** = added after the 6/25 decision, not yet confirmed.

| ID | Hazard | Asset | Impact | Status | Exposure inputs | Sensitivity indicators | Notes |
|----|--------|-------|--------|--------|-----------------|------------------------|-------|
| AV-R | Avalanche | Roads | OP | Include in VA | SNODAS / Topofire SWE; OpenTopography LiDAR + RAMMS runout | Road elevation (no unique sensitivity) | Initial focus: Hwy 89, 207, 431; confirm scope with NDOT/Caltrans |
| AV-B | Avalanche | Bridges | PC | Include in VA | | | |
| DF-B | Debris Flow | Bridges | PC | Include in VA | | | Added at the 6/25 VA review |
| DF-C | Debris Flow | Culverts | PC | Include in VA | Post-fire debris flow (HEC-HMS); CA Pyregence; precip (Cal-Adapt) | Culvert condition, capacity, scour | Split from landslide per 5/20; post-fire compounding required per ICF; WildCat modeling planned |
| DF-R | Debris Flow | Roads | PC | Include in VA | Post-fire debris flow (HEC-HMS); LiDAR runout; precip | Pavement condition, road elevation | Split from landslide per 5/20; July 14 event hindcast on the Storm Events page |
| FL-B | Flooding | Bridges | PC | Include in VA | HEC-RAS bridge scour; USGS StreamStats; FEMA floodplains | Bridge condition, deck rating/type, scour criticality, elevation, channel & water-opening adequacy | Bridge condition and scour criticality from the FHWA National Bridge Inventory |
| FL-C | Flooding | Culverts | PC | Include in VA | USGS StreamStats (peak discharge); NOAA Atlas 14; FEMA floodplains; HEC-RAS scour; lake stage as tailwater at shoreline outlets | Culvert condition, scour, capacity, age, channel condition | TRPA culvert layer compiled (7,858 assets, 6 jurisdictions); CULVERT screening on the Storm Events page. High lake stage reduces outlet capacity independent of rainfall |
| FL-R | Flooding | Roads | PC | Include in VA | FEMA floodplains; USGS StreamStats; HEC-RAS; road elevation vs. inundation | Pavement condition, foundation / permeable sub-base, elevation, age | Lowland and valley segments most exposed |
| LS-B | Landslide | Bridges | PC | Include in VA | | | |
| LS-C | Landslide | Culverts | PC | Include in VA | USGS Landslide Susceptibility; CA Geological Survey; post-fire debris-flow | Culvert condition, capacity, scour | Post-fire compounding required per ICF |
| LS-R | Landslide | Roads | PC | Include in VA | USGS Landslide Susceptibility; CA Geological Survey; LiDAR + RAMMS runout | Pavement condition, road elevation | Runout extents via RAMMS or r.avaflow |
| WF-AT | Wildfire | Active Transport | PC | Include in VA | | Paved vs. unpaved, trail slope | |
| WF-R | Wildfire | Roads | PC | Include in VA | Wildfire Risk to Communities; CA Pyregence; fire-weather index (Cal-Adapt); commercial fire modeling | No unique sensitivity indicators | Fire-modeling procurement is the critical-path dependency |
| WF-TC | Wildfire | Transit Centers | PC | Include in VA | | | |
| EQ-B | Earthquake | Bridges | PC | TRIP discussion | USGS Seismic Hazard Maps; ComCat; ShakeMaps | Seismic retrofit status, bridge condition, age | |
| EQ-R | Earthquake | Roads | PC | TRIP discussion | | | |
| FL-AT | Flooding | Active Transport | PC | TRIP discussion | | | |
| FL-TC | Flooding | Transit Centers | PC | TRIP discussion | | | Added at the 6/25 VA review |
| WF-M | Wildfire | Marinas | PC | TRIP discussion | | | |
| WD-R | Wind | Roads | OP | TRIP discussion | gridMET wind (Climate Engine); ASCE 7 | Operational: tree blow-down, power-line breaks | |
| WS-AT | Winter Storm | Active Transport | OP | TRIP discussion | | | |
| WS-R | Winter Storm | Roads | OP | TRIP discussion | SNODAS SWE; Cal-Adapt snow projections; NRI Winter Storm | Operational: extended closure, plow-depot overrun, ITS power loss | |
| WS-TC | Winter Storm | Transit Centers | OP | TRIP discussion | | | |
| SE-R | Seiche | Roads | PC | **Proposed** | TRPA bathymetry + wind models; USGS seismic | Road elevation above lake stage, shoreline armoring, pavement foundation | Shoreline routes: Hwy 28 and US-50 East Shore |
| SE-AT | Seiche | Active Transport | PC | **Proposed** | TRPA bathymetry + wind models | Elevation above lake stage, paved vs. unpaved | East Shore Trail and shoreline bike paths |
| LL-R | High Lake Level | Roads | PC | **Proposed** | TRPA Lake Tahoe at High Water (live); lake stage exceedance frequency | Road elevation, pavement foundation, depth to groundwater | Data live today; lake stage is regulated, so exceedance frequency is tractable |
| LL-AT | High Lake Level | Active Transport | PC | **Proposed** | TRPA Lake Tahoe at High Water (live) | Elevation above lake stage | Shoreline paths inundate at sustained high stand |

**Proposed** = added after the June 25 decision, pending Steering Committee confirmation. Seiche was
already tracked as a data element and rated in the asset and vulnerability matrix but had no pair,
which is the inconsistency these entries resolve. High lake level also acts as **tailwater at
shoreline culvert outlets**, reducing capacity independent of rainfall; that is carried as an
exposure input on FL-C rather than a separate culvert pair.

**Shallow groundwater is deliberately not a hazard.** It is a persistent site condition with no
event frequency, so it enters as a *sensitivity* attribute (depth to groundwater on roads and
culverts, alongside pavement foundation) rather than a pair. If groundwater rise under climate
change is modeled later, that becomes an exposure input beside Climate: Subsidence.

## 3. Screening indicators (6/25 deck, slide 6)

- **Sensitivity**: asset elevation (roads, bridges, culverts, active transport); pavement condition
  and foundation (roads); bridge condition, deck rating/type, material, scour criticality, seismic
  retrofit (bridges); culvert condition, scour, capacity (culverts); paved vs. unpaved, trail slope
  (active transport). The TRPA Equity Study (vulnerable populations) is applied as a Justice40
  multiplier.

  Condition sources: **bridges** from the FHWA National Bridge Inventory (public annual dataset, no
  agency request needed); **culverts** from the compiled TRPA layer and condition table (7,858
  assets, six jurisdictions); **pavement** is TBD, with jurisdiction outreach planned - the
  remaining sensitivity gap for the road pairs.
- **Criticality**: detour length and AADT (roads, bridges); proximity to strategic community
  assets and community priority zones (roads, bridges, culverts, active transport, transit
  centers).

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

37 data elements, each mapped to the assessment step it feeds (Step 1 Criticality, Step 2 Exposure,
Step 2 Sensitivity, Step 3 Disruption, or Context / TRIP for elements that support the plan or Task
3.4 rather than the scoring), plus the model/tool inventory, are catalogued in the **Data and Model
Inventory** tab of the [reference hub](html/reference-hub.html) (the source of record) and
`PROTECT_DataModel_Inventory.xlsx`. Not reproduced here to avoid divergence.

## 7. Open decisions

**Vendor risk scores versus this screening.** Both contracted datasets ship a pre-computed risk
score: an average-annual-loss measure for flood and a net-value-change measure for wildfire. Each is
structurally the same shape as (Exposure + Sensitivity) x Criticality. Recommendation: take the
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

Other headline items: exposure and sensitivity scoring rubrics per pair (finalize with screening
datasets, Aug 2026), scenario definitions for step 3 (after screening), analysis grain (segment
vs. parcel), climate-data sourcing for commercial flood data (TRPA purchase vs. add to ICF
contract), data hand-off contract, hosting domain, and public visibility. Climate-specific
decisions live on the [climate data page](html/climate-data.html) Open Decisions tab.
