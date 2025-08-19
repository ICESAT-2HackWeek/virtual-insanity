# Virtual Insanity Team

**Virtual Stores and Alternative Access Patterns to Mission Data**

This project will explore the potential use of VirtualiZarr, Geoparquet etc as means to improve access patterns to 
data from the ICESat-2 mission, especially the trajectory-based L2 datasets, ATL03, ATL06 and ATL08.
One of the premises is that these access patterns will make use the same HDF5 files as the data source (to avoid data duplication) and a layer of chunk manifests that will enable users to bypass the HDF5 library and use Zarr-compatible readers.

> Note: Project name based on Danny Kaufman's idea for [TEMPO+VirtualiZarr](https://earthaccess.readthedocs.io/en/latest/tutorials/virtual_dataset_tutorial_with_TEMPO_Level3/)

## Collaborators

Feel free to add more names!

| Name | Personal goals | Can help with | Role |
| ------------- | ------------- | ------------- | ------------- |
| Andy Barrett | I would like to <fill>        | ... | Contributor |
| Chuck Daniels | I would like to <fill>       | ... | Contributor  |
| Joe Kennedy | I would like to <fill>         | ... | Contributor |
| Miguel Jimenez-Urias | I would like to <fill>| ... | Contributor |
| Owen Littlejohns | I would like to <fill>    | ... | Contributor   |
| Luis Lopez | I woud like to push HDF5 to the limit, explore cloud native Geo-HDF5 | ... | Contributor/Project Lead |
| Ben Smith | I would like to <fill> | ... | Contributor |


## The problem

Accessing HDF5 in the cloud is slow, the lack of an spatial index in the HDF5 format, the architecture of the HDF5 client library and the nested structure of the data makes working with these datasets a challenge from the get-go, we would like to explore different ways of accessing trajectory data in HDF5 acknowledging that it would be better if we avoid full data duplication. We could also explore what gain we get if we just use Geoparquet or COPCI instead of HDF5. Knowing what works of could work will benefit other workflows from missions with big and/or complex trajectory data (e.g. NISAR, Tempo, GEDI etc). There are several PRs that need to be merged before we attempt to try some of the potential solutions so we'll have to use code from forks and not-yet-merged branches.

## Data and Methods

Subsetting a region of interest for ATL06(and hopefully ATL03) using the following polygon:

```json

{
"type": "FeatureCollection",
"name": "greenland_aoi",
"crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
"features": [
    { "type": "Feature",
      "properties": { },
      "geometry": { 
          "type": "Polygon",
          "coordinates": [ 
            [ 
              [ -45.379436701418982, 62.632384888224848 ],
              [ -44.620563298581018, 62.632384888224848 ],
              [ -44.615470340415492, 62.981973185442563 ],
              [ -45.384529659584508, 62.981973185442563 ],
              [ -45.379436701418982, 62.632384888224848 ] 
            ] 
          ] 
      }
    }
  ]
}
```

The result of our experiment should be a geoparquet file with all the photon data from the 6 ground tracks containing the following variables in the dataframe:

* **ATL06**: lat, long, time, h_li, h_li_sigma, atl06_quality_summary, track_id
* **ATL03**: TBD (Optional for this week)
* **ATL08**: TBD (Optional for this week)

## Existing methods

### 1. SlideRule: As of now this would be the best case scenario to [subset a ROI](https://github.com/ICESAT-2HackWeek/icesat2-cookbook/blob/main/notebooks/draft/workflows/greenland_dhdt/dhdt_40km_tile.ipynb)
* SlideRule is very efficient on getting the data in parallel thanks to the use of an elastic cluster and the [H5Coro](https://github.com/SlideRuleEarth/h5coro) client library. This library uses a pool of threads to fetch data concurrently bypassing the HDF5 client library limitations. 
* The only downside of SlideRule is that it requires a service and thus there is an overhead in terms of costs and maintainability. 
* Time to a Geoparquet file using our Greenland ROI (ATL06): **30 seconds**

### 2. Harmony Trajectory Subsetter:
* We haven't benchmarked the Harmony subsetter yet, we assume we could get better results than downloading and subsetting but probably not as fast as SlideRule.

### 3. Cloud OPeNDAP
* Similar to Harmony, loading the data should be faster than downloading and subsetting in the client side, we'll have to measure if the subsetting is as fast as SlideRule.

## Proposed methods/tools

As we can notice, the subsetting in the current methods relies on services, one of the advantages of cloud native formats is that we could push that to the client and take advantage of the metadata to do spatial operations "on-the-fly" without having to need a service.

### 1. Baseline: search and access using earthaccess, subset the data with geopandas or xarray. 

* This would be the "naive" approach and will require to load full trajectories into memory to do the spatial filtering after having them into a dataframe. 
* There are 6 trajectories per file, each trajectory from the overlapping files needs to be subsetted.
* V7 is cloud optimized but ATL06 still uses V6
* We can use fsspec form this PR to improve the fetching and caching of bytes in `earthaccess.open()`: [PR 1061](https://github.com/nsidc/earthaccess/pull/1061)

> Improvements: the one improvement we test here is that fsspec could potentially give us enough performance that loading the whole trajectory should be Ok as long as we have enough memory.

### 2. VirtualiZarr: Trying to use dmrpp files to load the metadata fast and access chunks in the HDF5 files using Zarr

* This has been tested with regular gridded data (L4) with good results, aggregation into a logical cube is tricky with point cloud data. 
* NSIDC is producing a somewhat outdated flat version of the dmrpp files, in order to read the dmrpp with VirtualiZarr we need to use code from [this PR](https://github.com/zarr-developers/VirtualiZarr/pull/757)
* Once we open the dmrpp files in the current state of things, we'll see a long flattened list of variables in our Xarray dataframe. 
* The loading of the metadata should be a little faster than reading the entire file but we still need to load the whole trajectory to do the spatial filtering. (None of the HDF5 at NASA has a build-int spatial index at the chunk level AFAIK)
* After we open our VirtualiZarr store using Miguel's PR we could try to serialize the chunk manifest into Parquet and try to open them with the Zarr reader. V3 should be faster thanks to the new async code (see PR [#967](https://github.com/nsidc/earthaccess/pull/967))

### 3. Spatially-aware virtual references: Looking into geoparquet with spatial information at the chunk level.

* HDF5 doesn't come with spatial indexes out of the box, one of the key aspects of cloud native geo is the ability to use an spatial index to sbset on the fly without having to fetch all the chunks first. 
* dmrpp doesn't include spatial information at the chunk level so this is something that we'll have to extract from the file and use in a geoparquet output.
* We won't have to think at the file level, we could use a non overlapping grid to aggregate chunks spatially e.g. Uber's H3 grid
* If this could be incorporated into the HDF5 files users could use the index to do the same thing without use having to mantain a geoparquet chunk index. This is something Ben mentioned he did for a personal project. 

### Additional resources or background reading

Optional: links to manuscripts or technical documents providing background information, context, or other relevant information.

### Project goals and tasks

### Project goals

List the specific project goals or research questions you want to answer. Think about what outcomes or deliverables you'd like to create (e.g. a series of tutorial notebooks demonstrating how to work with a dataset, results of an anaysis to answer a science question, an example of applying a new analysis method, or a new python package).

* Goal 1
* Goal 2
* ...

### Tasks

What are the individual tasks or steps that need to be taken to achieve each of the project goals identified above? What are the skills that participants will need or will learn and practice to complete each of these tasks? Think about which tasks are dependent on prior tasks, or which tasks can be performed in parallel.

* Task 1 (all team members will learn to use GitHub)
* Task 2 (team members will use the scikit-learn python library)
  * Task 2a (assigned to team member A)
  * Task 2b (assigned to team member B)
* Task 3
* ...

## Project Results

Use this section to briefly summarize your project results. This could take the form of describing the progress your team made to answering a research question, developing a tool or tutorial, interesting things found in exploring a new dataset, lessons learned for applying a new method, personal accomplishments of each team member, or anything else the team wants to share.

You could include figures or images here, links to notebooks or code elsewhere in the repository (such as in the [notebooks](notebooks/) folder), and information on how others can run your notebooks or code.
