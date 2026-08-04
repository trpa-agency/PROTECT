# Scoping archive: spring 2026 working notes

Retired from `html/reference-hub.html` on Aug. 3, 2026 during the site refactor. These were
early-scoping working notes published verbatim on the hub's first tab. The material they informed
now lives in more mature form elsewhere: the Data and Model Inventory tab (source of record for
data readiness), the Exposure Datasets tab (per-hazard dataset evaluation from the 4/30 ICF data
meeting), and the Criticality Index app (segment criticality scoring, which settled several of the
"how to score criticality" questions below). Kept here as the record of early thinking.

## Assets (criticality and vulnerability scoping)

| Asset | How to score criticality | Additional vulnerability values | Comments |
|---|---|---|---|
| Active Transport | Maybe a network analysis or just expense of replacement? | | |
| Bridges | From road segment values | Age or National Bridge Inventory data | |
| Culverts | Get criticality from Road criticality of section they are on | Possibly county or transportation department condition information | |
| Marinas | Size? This could be weird since they are privately owned | | |
| Roads | Traffic counts, RA2CE detour and impact of disruption analysis | DOT road condition information? | This is going to be the hard one |
| Transit Centers | Size/Number of passengers served | | |

Resolution notes (Aug. 2026): road-segment criticality is now scored interactively in
`html/criticality-index.html` (18,253 segments, adjustable weights); bridges and culverts inherit
their segment's score per the framework; the culvert condition question was answered by the
compiled six-jurisdiction culvert layer (`outputs/culverts.gdb`, 7,858 assets).

## Hazard data sources (early evaluation)

| Hazard | Data source | TRPA status | Link | Details |
|---|---|---|---|---|
| Avalanche | RAMMS::Avalanche | Need to buy | | |
| Fire | Wildfire Exposure | Have | Forest_Health_Composition_Age/MapServer | Wildfire Risk to Communities; CA Pyregence; CA Forest Observatory |
| Fire | Completed forest thinning | Have | TFFT | Use this to adjust wildfire risk |
| Fire | Fire Behavior Modeling | Purchase | Commercial vendors (RFP) | |
| Flooding | NOAA Flood Zones | Have | Streams_and_Flood_Zone/MapServer | |
| Flooding | HEC-RAS (USACE) | Free but requires work | | |
| Landslide | WEPP | Have? | | |
| Landslide | USGS Landslide Susceptibility | | | Need more details |
| Wind | gridMET wind | | | Need more details |
| Winter Storm | Unknown | | | |
| Winter Storm | SNODAS SWE | | | Need more details |
| Winter Storm | Snow plow route info | | | |

Resolution notes (Aug. 2026): the open questions here were superseded by the Exposure Datasets
evaluation (4/30 ICF data meeting) on the hub, which names a primary dataset per hazard and flags
availability. WEPP is confirmed in use (post-fire erosion / sediment chain on the Storm Events
page); SNODAS / SWE went to the avalanche exposure approach; RAMMS remains a sole-source purchase
candidate for runout zones.
