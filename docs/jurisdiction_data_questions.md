# Culvert Data - Questions for Jurisdictions

Follow-up items from building the basin-wide culvert layer (`notebooks/culvert_layer_engineering.ipynb`,
run 2026-07-29). Organized by jurisdiction, roughly in priority order. Counts refer to the
delivered data after clipping to the TRPA boundary.

## Douglas County - coverage gap (highest priority)

The delivery is county-wide. Its Tahoe area (`Area = 'Tahoe'`) holds 286 records, but they are
almost entirely water-quality features: 129 drop inlets, 93 manhole covers, 23 basins,
19 Vortechs units, 18 other - and only **4 records typed `1 - Culvert`** (the only 4 with a
culvert material). Ask:

1. Is 4 the real count of county-maintained culverts in the basin, or are Tahoe cross-drains
   typed under `2 - Drop Inlet` / `6 - Other` in this inventory?
2. Are Tahoe-side road culverts in Douglas County owned/maintained by the GIDs (Kingsbury,
   Round Hill, Zephyr Cove, etc.) or NDOT rather than the county? If the GIDs, who holds those
   inventories and can they be added to the data request?
3. Confirm the maintenance score (1 = replacement ... 5 = none needed) is the closest thing to
   a condition rating, or whether structural condition is tracked separately.
4. 30 county-wide inspection records lack the `GID_Join` asset key - can these be linked to
   assets?

## El Dorado County

1. **Domain lookups**: the delivered README was empty. Need the coded-value definitions for
   `MATL_CODE`, `TYPE_SHAPE_CODE`, `INLET_TREATMENT_CODE`, `OUTLET_TREATMENT_CODE`,
   `TYPE_PWALL_CODE`, and `STATUS` in `SW_PIPE`.
2. Which SW_PIPE features are road culverts vs. buried storm drain? There is no feature-type
   field; all 2,615 basin pipes are currently tagged `stormwater pipe`.
3. Is there any condition or inspection data? None was delivered.
4. Confirm `STOP_DATE_CODE = 1` means retired/abandoned (those 49 were dropped).

## Washoe County

1. The `condition` field in Condition.dbf is 0 for all 1,716 records - is that intended, and
   which field carries the overall rating?
2. What is the scale for the subscores (`Structural`, `Blockage`, `Shoulder`, etc. - values
   0, 2, 3, 4, 5 observed)? Is 2 "good"?
3. Only 806 of 2,413 conveyance pipes have condition records - are the rest uninspected, or
   is there more inspection history?
4. The GNSS length fields are zeros and `FV_Date` is a placeholder (1899-12-31) - is geometry
   length the authoritative pipe length?

## Placer County

1. The 1-5 `Condition` rating: which end is good? (Distribution: mostly 4s and 5s.)
2. `Pipe_Material` is ~99% empty - is material tracked in another system?
3. 9 `STID_PM` values repeat - multiple barrels at one crossing, or duplicate records?
4. `INSTALL_DATE` is almost entirely empty - is install year available anywhere?

## Caltrans District 3

1. The drainage inventories include inspection dates but no condition ratings - can D3 share
   ratings from the culvert inspection program for these routes?
2. Some inspections date to 2006 (US-50 segment) - is newer inspection data available?
3. Confirm the row-per-segment model: rows sharing a `SYSNO` were combined into one culvert
   (lengths summed, location at first inlet).

## City of South Lake Tahoe

1. The Stormwater FeatureServer has inspection tables for outfalls, catch basins, BMPs, and
   manholes but none for culverts - do culvert inspections exist elsewhere?
2. Only 40 culverts citywide (32 in service) - is the culvert layer a complete inventory, or
   are some crossings mapped in the Pipe layer?
3. Some culverts are flagged `ownedby = CalTrans` - confirm how ownership overlap with the
   D3 inventory should be handled to avoid double counting.

## NDOT

1. Execute the pending data sharing agreement.
2. Request culvert locations and condition for US-50, SR-28, SR-207, and SR-431 within the
   basin, including the inspection scale used.
