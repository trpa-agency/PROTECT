# PROTECT: Hazard x Asset Pairs & Risk Index (v0.3)

**Task 3.3 Interactive Risk Index Mapping Tool** (PROTECT Plan, Task 3 Resilience Improvement Plan)

Plain-text source-of-record for the hazard-asset pairs and modeling approach. The interactive
version (with the data inventory, model inventory, and full framework) lives at
[`html/index.html`](html/index.html).

The risk index follows the **FHWA VAST framework**. Four sub-indices (Exposure, Sensitivity, Asset
Value, and Adaptive Capacity, reverse-scored) combine into a **Master PROTECT Index**, weighted
alongside Criticality. Per ICF guidance, Sensitivity is weighted lightly (about 10-20 percent) and
Criticality substantially (about 30 percent, just below Exposure).

Sources: 5/20/2026 ICF/TRPA VA deck (sensitivity & criticality approach),
`PROTECT_DataModel_Inventory.xlsx`, `PROTECT_RiskIndexTool_Scoping_v0.1.docx`.

> v0.3 supersedes v0.2 (which used Risk = Vulnerability x Criticality and 9 pairs). v0.3 adopts the
> FHWA VAST four-sub-index model and the expanded asset/hazard scope confirmed at the 5/20 sync.

---

## 1. Hazard x Asset pairs (working list)

Impact: **PC** = physical damage + cascading operational disruption; **OP** = operational only.
Status: **Advancing** (locked at the VA review), **Candidate** (added 5/20, under review),
**Screening** (asset target / scope still TBD).

| ID | Hazard | Asset | Impact | Status | Exposure inputs | Sensitivity indicators | Notes |
|----|--------|-------|--------|--------|-----------------|------------------------|-------|
| FL-C | Flooding | Culverts | PC | Advancing | HEC-RAS scour; USGS StreamStats; FEMA; NOAA Atlas 14 | Culvert condition, scour, capacity, age | Caltrans/NDOT condition request open |
| FL-R | Flooding | Roads | PC | Advancing | FEMA; stormwater drainage; road elevation vs. inundation | Pavement condition, foundation, elevation, age | Lowland/valley segments most exposed |
| FL-B | Flooding | Bridges | PC | Advancing | HEC-RAS bridge scour; USGS StreamStats; FEMA | Bridge condition, deck, scour criticality, elevation | Bridge condition request open |
| AV-R | Avalanche | Roads | PC | Advancing | RAMMS::Avalanche runout; OpenTopography LiDAR | Road elevation (no unique sensitivity) | Hwy 89, 207, 431; confirm with NDOT/Caltrans |
| LS-C | Landslide | Culverts | PC | Advancing | Slope + erosion + burn severity; post-fire debris flow | Culvert condition, capacity, scour | Post-fire compounding required |
| LS-R | Landslide | Roads | PC | Advancing | Slope + erosion + burn severity; LiDAR runout | Pavement condition, road elevation | RAMMS or r.avaflow runout |
| WF-R | Wildfire | Roads | PC | Advancing | Wildfire severity; soil burn severity; ember showers; fire pathways (XyloPlan / Land Tender) | No unique sensitivity indicators | XyloPlan procurement on critical path |
| DF-C | Debris Flow | Culverts | PC | Candidate | Post-fire debris-flow runout; slope + burn severity | Culvert condition, capacity, scour | Split from landslide per 5/20 |
| DF-R | Debris Flow | Roads | PC | Candidate | Post-fire debris-flow runout; slope + burn severity; LiDAR | Pavement condition, road elevation | Split from landslide per 5/20 |
| EQ-B | Earthquake | Bridges | PC | Candidate | USGS faults; liquefaction; dam inundation | Seismic retrofit status, bridge condition, age | Bridges needing seismic retrofit |
| WD-R | Wind | Roads | OP | Screening | gridMET wind + USFS canopy strike zones; ASCE 7 | Operational: tree blow-down, power-line breaks | Asset TBD: Roads and/or Power & Telecom |
| WS-R | Winter Storm | Roads | OP | Screening | Plow-route distance; Cal-Adapt snow; power-loss frequency | Operational: closure, plow-depot overrun, ITS power loss | Asset TBD: Roads / Power / ITS |

Expanded assets still under screening (no pair locked yet): **Active Transport, Bus Stops, Marinas**.

---

## 2. Vulnerability sub-indices (FHWA VAST)

- **Exposure**: where and how intensely a hazard hits. XyloPlan (fire pathways), HEC-RAS / StreamStats
  (flood inundation & scour), RAMMS (avalanche / landslide / debris-flow runout), WEPP (post-fire soil
  erosion and sediment delivery), wind strike zones, seiche zones, seismic / dam inundation.
- **Sensitivity** (weighted ~10-20 percent): asset fragility. Bridge / culvert condition, pavement
  age, road elevation; stormwater / IDF capacity. The TRPA Equity Study (vulnerable populations) is
  applied as a Justice40 multiplier.
- **Asset Value**: what is at stake. Strategic community assets, emergency staging, freight tonnage,
  transit, active transport, cascading assets (power, telecom).
- **Adaptive Capacity** (reverse-scored: high capacity = low vulnerability): network redundancy /
  detour ratios (StreetLight), redundant power (HIFLD), transit hubs, airport ICS proximity.

## 3. Criticality indicators

- **Roads** (DCTC / MWCOG): AADT, proximity to strategic community assets, community priority zones
  (TRPA-developed), detour length, transit & bike facilities on the asset. Bridges and culverts on a
  segment inherit the road's score.
- **Active Transportation**: proximity to strategic assets and other modes, community priority zones,
  emergency-vehicle accommodation.
- **Bus Stops**: ridership, community priority zones, proximity to strategic assets, multi-modal
  connectivity (or inherit the road segment's score).

## 4. Composite index architecture

`A. Exposure` + `B. Sensitivity` + `C. Asset / Adaptive Capacity (reverse)` -> `D. Master PROTECT Index`
(the single composite map for the Task 3.3 interactive tool).

## 5. Disruption-risk tool (under evaluation)

**RA2CE** (Deltares; flexible Python framework, direct + indirect detour costs) vs. **Volpe RDR**
(USDOT; ROI / system-performance, heavier data and effort). ICF is preparing a pros/cons comparison
and level-of-effort estimate; TRPA is reviewing both. Decision needed before the MVP build.

## 6. Data inventory

33 data elements mapped to VAST components (including a planned **WEPP** erosion/sediment service),
plus a model/tool inventory (RA2CE, Volpe RDR, the Overture street network, WEPP, and others) and the
composite-index architecture, are catalogued in the **Data Inventory** tab of
[`html/index.html`](html/index.html), the full tracker
[`html/data-model-inventory.html`](html/data-model-inventory.html), and `PROTECT_DataModel_Inventory.xlsx`.
Not reproduced here to avoid divergence.

## 7. Open decisions

See the **Open Decisions** tab of the tool. Headline items: disruption-risk tool (RA2CE vs. Volpe RDR),
which pairs advance to robust geospatial analysis, exposure scoring rubric per hazard, analysis grain
(segment vs. parcel), climate-data sourcing (TRPA purchase vs. add to ICF contract; Fathom flood data
about $29,543), ICF endorsement of the VAST structure, data hand-off contract, hosting domain, and
public visibility.
