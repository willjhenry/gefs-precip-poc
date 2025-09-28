#!/usr/bin/env python3
"""
AWS GEFS Ensemble Precipitation Data Downloader

Downloads GEFS ensemble precipitation data for Rhine basin point location.
Processes 30 perturbed members + control + spread + mean for 5-7 day forecasts.
Sequential processing with resume capability and memory-efficient operation.

Usage:
    python download_gefs_ensemble.py --start-date 2024-01-01 --end-date 2024-01-31
    python download_gefs_ensemble.py --resume  # Resume from checkpoint

Notes:
    - GRIB files are downloaded to `data/interim/gefs/` (temporary working files)
    - Extracted CSV is saved to `data/processed/gefs_ensemble_tp.csv`
    - Log and checkpoint files are stored in the `scripts/` directory
"""

import argparse
import logging
import os
import sys

from hydro.common import RHINE_POINT, SCRIPTS_DIR
from hydro.data_processing.gefs_downloader import GEFSDownloader

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

    gefs_downloader = GEFSDownloader(
        location=RHINE_POINT,
        start_date=args.start_date,
        end_date=args.end_date,
        test=args.test,
        logger=logger,
    )
    gefs_downloader.download(resume=args.resume)


if __name__ == "__main__":
    main()
