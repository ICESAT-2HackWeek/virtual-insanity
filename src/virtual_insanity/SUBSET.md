# Subsetting

**Prerequisite:** [Install pixi](https://pixi.sh/latest/installation/)

The "naive subsetter" does the following:

- Queries the NASA CMR for granules from the ATL06 collection
  (C2670138092-NSIDC_CPRD) within a bounding box in Greenland
  (-45.38452, 62.63238, -44.61547, 62.98197).
- For each granule, is selects variables/datasets within all 6 tracks and clips
  the result to the bounding box
- Concatenates all subsetted granules into a single GeoDataFrame and writes it
  all to a parquet file.

See `parameters.py` for details on tracks and variables.

If using S3 URLs (see help below), you must set the environment variable
`EARTHDATA_TOKEN` to an active Earthdata Login token.

Run the following to see available options:

```plain
pixi run subset -h
```
