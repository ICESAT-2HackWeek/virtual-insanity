# Subsetting

This "naive" subsetter is intended to see how much performance we can squeeze
out of a simple implementation of a spatio-temporal subsetter of ICESat-2 data
(although, this is likely general enough to adapt to other similar data).  By
"naive," we mean code that uses only libraries necessary for reading the data
files via HTTPS or S3, without the aid of any non-ephemeral cloud services.

The aim is to see how close we can get to the performance of services such as
SlideRule (in particular) and Harmony, without the need for "heavy" services.

As a target, SlideRule is able to perform the subsetting described below in
approximately 25-30 seconds.

The subsetter does the following:

- Queries the NASA CMR for granules from the ATL06 collection
  (C2670138092-NSIDC_CPRD) within a bounding box in Greenland
  (-45.38452, 62.63238, -44.61547, 62.98197).
- For each granule, selects variables/datasets within all 6 tracks and clips
  the result to the bounding box.
- Concatenates all subsetted granules into a single GeoDataFrame and writes it
  all to a parquet file.

See `src/virtual_insanity/parameters.py` for details on tracks and variables.

## Prerequisites

- [Install pixi](https://pixi.sh/latest/installation/)
- Create an [Earthdata Login](https://urs.earthdata.nasa.gov/) (EDL) account
- Create an EDL Token (navigate to the "Generate Token" link in your EDL profile)
- Copy your EDL token and export it as the value of the environment variable
  `EARTHDATA_TOKEN`

## Generating a Subset

Run the following to see available options:

```plain
pixi run subset -h
```

By default, HTTPS URLs are used to read data files, but when running in an AWS
environment within the `us-west-2` region, you may specify the `--s3` option to
fetch data via S3 URLs instead.  Using S3 URLs can provide up to ~2x speedup.

For example:

```plain
pixi run subset subset-s3.parquet --s3
```

> [!TIP]
>
> If you want to first make sure you have things configured correctly, you can
> limit the number of granules to subset by using the `-l` (`--limit`) option
> (with or without the `--s3` option):
>
> ```plain
> pixi run subset sample.parquet --limit 1
> ```
>
> This will subset only 1 granule, instead of all of the granules within the
> AOI.

By default files are read in parallel across all available CPUs (i.e., the code
will use 1 process per available CPU).  However, you may use the `-p`
(`--processes`) option to specify how the number of processes to use (either
more or fewer than available CPUs).

> [!CAUTION]
>
> As a rough guide for balancing peak memory requirements with parallelization,
> make sure your machine has a minimum of ~1.8GB of RAM per process.  This
> should provide enough headroom to avoid excessive memory pressure (or even
> completely running out of memory) that may slow (or halt) the subsetter.
>
> For example, if running in a Hub instance where you have only 4 CPUs
> available, make sure you can choose a configuration with at least ~7GB of RAM.
>
> However, this does not mean you are limited to only as many processes as
> available CPUs.  To a _limited extent_, specifying a number of processors
> _greater_ than the number of available CPUs can improve performance, as long
> as you have enough memory available.
>
> For example, using the same Hub instance with only 4 CPUs, if you configure
> the instance with ~15GB of RAM, you should see a significant speedup by
> specifying `-p 8` on the command line (not quite a 2x speedup over 4
> processes, but not far off).
