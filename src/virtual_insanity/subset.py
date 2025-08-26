import logging
import multiprocessing as mp
import os
import typing as t
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor

import fsspec
import geopandas as gpd
import h5py
import pandas as pd

logger = logging.getLogger(__name__)


class SelectFromGranuleKwargs(t.TypedDict):
    url: str
    fsspec_kwargs: dict[str, t.Any]
    group_names: Sequence[str]
    dataset_names: Sequence[str]
    lon_name: str
    lat_name: str
    bbox: tuple[float, float, float, float]


def set_log_level(logger: logging.Logger, level: int) -> None:
    logger.setLevel(level)


def select_from_granules(
    urls: Sequence[str],
    fsspec_kwargs: dict[str, t.Any],
    *,
    group_names: Sequence[str],
    dataset_names: Sequence[str],
    lon_name: str,
    lat_name: str,
    bbox: tuple[float, float, float, float],
    n_workers: int | None = None,
) -> gpd.GeoDataFrame:
    kwargss = (
        SelectFromGranuleKwargs(
            url=url,
            fsspec_kwargs=fsspec_kwargs,
            group_names=group_names,
            dataset_names=dataset_names,
            lon_name=lon_name,
            lat_name=lat_name,
            bbox=bbox,
        )
        for url in urls
    )

    level = logging.INFO
    set_log_level(logger, level)

    with mp.Pool(
        processes=n_workers,
        initializer=set_log_level,
        initargs=(logger, level),
    ) as pool:
        processes = pool._processes  # pyright: ignore[reportAttributeAccessIssue]
        chunksize = min(10, max(1, len(urls) // processes))
        logger.info(f"Using {processes} processes with chunksize {chunksize}")
        gdfs = pool.imap_unordered(select_from_granule, kwargss, chunksize=chunksize)

        return t.cast(gpd.GeoDataFrame, pd.concat(gdfs, ignore_index=True, copy=False))


def select_from_granule(kwargs: SelectFromGranuleKwargs) -> gpd.GeoDataFrame:
    fs: fsspec.AbstractFileSystem
    fs, _ = fsspec.url_to_fs(kwargs["url"], **kwargs["fsspec_kwargs"])

    logger.info(f"Reading {kwargs['url']}")

    try:
        gdf = geodataframe_from_h5file(
            fs,
            kwargs["url"],
            group_names=kwargs["group_names"],
            data_paths=kwargs["dataset_names"],
            lon_path=kwargs["lon_name"],
            lat_path=kwargs["lat_name"],
        ).clip(kwargs["bbox"])
    except Exception as e:
        # To avoid a pickling problem with exceptions raised from aio-libs (via
        # fsspec+aiohttp), we'll log exceptions and simply raise RuntimeErrors
        # instead.  See https://github.com/aio-libs/multidict/issues/340.
        e.add_note(f"Unable to read {kwargs['url']}")
        raise

    logger.info(f"Selected {len(gdf)} rows from {kwargs['url']}")

    return gdf


def geodataframe_from_h5file(
    fs: fsspec.AbstractFileSystem,
    url: str,
    *,
    group_names: Iterable[str],
    data_paths: Iterable[str],
    lon_path: str,
    lat_path: str,
) -> gpd.GeoDataFrame:
    with fs.open(url) as f, h5py.File(f) as hdf5:
        gdfs = (
            geodataframe_from_h5group(
                t.cast(h5py.Group, hdf5[group_name]),
                dataset_names=data_paths,
                lon_name=lon_path,
                lat_name=lat_path,
            )
            for group_name in group_names
        )

        return t.cast(gpd.GeoDataFrame, pd.concat(gdfs, ignore_index=True, copy=False))


def geodataframe_from_h5group(
    group: h5py.Group,
    *,
    dataset_names: Iterable[str],
    lon_name: str,
    lat_name: str,
) -> gpd.GeoDataFrame:
    x, y, *columns = select_from_group(group, [lon_name, lat_name, *dataset_names])
    data = {series.name: series for series in columns}
    geometry = gpd.points_from_xy(x, y)

    return gpd.GeoDataFrame(data, geometry=geometry)


def select_from_group(
    group: h5py.Group,
    dataset_paths: Iterable[str],
) -> Sequence[pd.Series]:
    datasets = map(lambda path: t.cast(h5py.Dataset, group[path]), dataset_paths)
    return tuple(map(series_from_dataset, datasets))


def series_from_dataset(ds: h5py.Dataset) -> pd.Series:
    name = dataset_basename(ds)
    return pd.Series(data=ds, name=name, dtype=ds.dtype)


def dataset_basename(ds: h5py.Dataset) -> str:
    return str(ds.name).rsplit("/", 1)[-1]
