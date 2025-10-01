#!/usr/bin/env python3
"""
ERA5 Data Downloader

Downloads ERA5 reanalysis data for Rhine basin point location.
Supports precipitation (tp) and temperature (t2m) variables.

Usage:
    python download_era5.py --variable tp --start-date 2025-01-01 --end-date 2025-01-31
    python download_era5.py --variable t2m --start-date 2025-01-01 --end-date 2025-01-31

Requires:
    pip install cdsapi
    CDS API credentials in ~/.cdsapirc or environment variables
"""

import argparse
import logging
import os
import sys

from hydro.common import GRID_RHINE_POINT, SCRIPTS_DIR
from hydro.data_processors.era5_downloader import Era5Downloader

LOG_FILE = os.path.join(SCRIPTS_DIR, "era5_download.log")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download ERA5 reanalysis data"
    )
    parser.add_argument(
        "--variable",
        required=True,
        choices=["tp", "t2m"],
        help="Variable to download: tp (precipitation) or t2m (temperature)",
    )
    parser.add_argument(
        "--start-date", required=True, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", required=True, help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=GRID_RHINE_POINT[0],
        help="Latitude for download (default: GRID_RHINE_POINT)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=GRID_RHINE_POINT[1],
        help="Longitude for download (default: GRID_RHINE_POINT)",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("Starting ERA5 data download")
    logger.info(f"Variable: {args.variable}")
    logger.info(f"Date range: {args.start_date} to {args.end_date}")
    logger.info(f"Location: lat={args.lat}, lon={args.lon}")

    try:
        downloader = Era5Downloader(
            location=(args.lat, args.lon),
            logger=logger,
        )
        downloaded_file = downloader.download(
            variable=args.variable,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        logger.info(f"ERA5 download completed successfully: {downloaded_file}")

    except Exception as e:
        logger.error(f"ERA5 download failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
