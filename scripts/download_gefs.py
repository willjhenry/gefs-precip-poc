#!/usr/bin/env python3
"""
AWS GEFS Ensemble Precipitation Data Downloader

Downloads GEFS ensemble precipitation data for Rhine basin point location.
Processes 30 perturbed members + control + spread + mean for 5-7 day forecasts.
Sequential processing with resume capability and memory-efficient operation.

Usage:
    python download_gefs.py --start-date 2024-01-01 --end-date 2024-01-31
    python download_gefs.py --start-date 2024-01-01 --end-date 2024-01-31 --start-hour 120 --end-hour 168
    python download_gefs.py --resume  # Resume from checkpoint

Notes:
    - GRIB files are downloaded to `data/interim/gefs/` (temporary working files)
    - Extracted CSV is saved to structured directory: `data/processed/gefs/lat-<lat>_lon-<lon>/lead_<start>-<end>/`
    - Log and checkpoint files are stored in the `scripts/` directory
"""

import argparse
import logging
import os
import sys

from hydro.common import GRID_RHINE_POINT, SCRIPTS_DIR
from hydro.data_processors.gefs_downloader import GEFSDownloader

LOG_FILE = os.path.join(SCRIPTS_DIR, "gefs_download.log")


"""Set up logging configuration."""
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download GEFS ensemble precipitation data"
    )
    parser.add_argument(
        "--start-date", required=True, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", required=True, help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--start-hour",
        type=int,
        default=120,
        help="Start forecast hour (default: 120)",
    )
    parser.add_argument(
        "--end-hour",
        type=int,
        default=168,
        help="End forecast hour (default: 168)",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from checkpoint"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test with single date and limited members",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Generate forecast hours list from start to end hour (3-hour intervals)
    forecast_hours = list(range(args.start_hour, args.end_hour + 1, 3))

    gefs_downloader = GEFSDownloader(
        location=GRID_RHINE_POINT,
        start_date=args.start_date,
        end_date=args.end_date,
        forecast_hours=forecast_hours,
        test=args.test,
        logger=logger,
    )
    gefs_downloader.download(resume=args.resume)


if __name__ == "__main__":
    main()
