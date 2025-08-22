#!/usr/bin/env python
import argparse
import earthaccess
import logging
import requests
from pathlib import Path

from virtual_insanity import subset
from virtual_insanity import parameters

logging_format = "[%(levelname)s][%(name)s:%(processName)s:%(threadName)s] %(message)s"
logging.basicConfig(level=logging.WARN, format=logging_format)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_s3_credentials(credentials_url: str, *, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    with (
        requests.Session() as session,
        session.get(credentials_url, allow_redirects=False, headers=headers) as request,
    ):
        request.raise_for_status()

        if request.is_redirect:
            # We were redirected, so the token is invalid or expired
            raise ValueError("invalid or expired Earthdata Login token")

        creds = request.json()

        return dict(
            key=creds["accessKeyId"],
            secret=creds["secretAccessKey"],
            token=creds["sessionToken"],
        )


def parse_args(args: list[str]):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=-1,
        help="Number of granules in AOI to subset",
    )
    parser.add_argument(
        "--s3",
        action="store_true",
        help="Use S3 URLs rather than HTTPS URLs",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="File to write geoparquet results to (e.g., subset.parquet)",
    )

    return parser.parse_args(args)


def main(*, s3: bool, count: int, output: Path):
    import os

    granules = earthaccess.search_data(
        concept_id=parameters.collection_concept_id,
        bounding_box=parameters.bbox,
        count=count,
    )

    logger.info(f"Subsetting {len(granules)} granule(s)")

    # Get URLs for each granule and flatten to a single list
    access = "direct" if s3 else "external"
    urlss = map(lambda g: g.data_links(access=access), granules)
    urls = [url for urls in urlss for url in urls]

    fsspec_kwargs = (
        dict(
            default_cache_type="background",
            default_block_size=8 * 1024 * 1024,
            **get_s3_credentials(
                "https://data.nsidc.earthdatacloud.nasa.gov/s3credentials",
                token=os.environ["EARTHDATA_TOKEN"],
            ),
        )
        if s3
        else dict(
            cache_type="background",
            block_size=8 * 1024 * 1024,
            client_kwargs={"trust_env": True},
        )
    )

    # Sample URLs for reference:
    #
    # s3://nsidc-cumulus-prod-protected/ATLAS/ATL06/006/2018/10/14/ATL06_20181014064703_02390105_006_02.h5
    # https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/ATLAS/ATL06/006/2018/10/14/ATL06_20181014064703_02390105_006_02.h5

    gdf = subset.select_from_granules(
        urls,
        fsspec_kwargs,
        group_names=parameters.group_names,
        dataset_names=parameters.dataset_names,
        lon_name=parameters.lon_name,
        lat_name=parameters.lat_name,
        bbox=parameters.bbox,
    )

    logger.info(f"Writing results to {output}")
    gdf.to_parquet(output)


if __name__ == "__main__":
    import sys

    ns = parse_args(sys.argv[1:])
    kwargs = dict(ns._get_kwargs())
    main(**kwargs)
