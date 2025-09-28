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

import cdsapi

from hydro.common import GRID_RHINE_POINT

# Paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_ERA5_DIR = os.path.join(DATA_DIR, "raw", "era5")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

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


def download_era5_data(
    variable: str,
    start_date: str,
    end_date: str,
    output_dir: str = RAW_ERA5_DIR,
) -> str:
    """
    Download ERA5 data for specified variable and date range.

    Args:
        variable: 'tp' for total_precipitation or 't2m' for 2m_temperature
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_dir: Output directory for downloaded files

    Returns:
        Path to downloaded file
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Map variable names
    variable_map = {"tp": "total_precipitation", "t2m": "2m_temperature"}

    if variable not in variable_map:
        raise ValueError(f"Unknown variable: {variable}. Use 'tp' or 't2m'")

    cds_variable = variable_map[variable]

    # Generate date range string for CDS API
    # CDS API expects format like "2025-01-01/2025-01-31"
    date_range = f"{start_date}/{end_date}"

    # Output filename
    output_file = os.path.join(
        output_dir,
        f"era5_{variable}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.nc",
    )

    logger.info(f"Downloading ERA5 {variable} data for {date_range}")
    logger.info(f"Location: {GRID_RHINE_POINT}")
    logger.info(f"Output: {output_file}")

    # CDS API request
    dataset = "reanalysis-era5-single-levels-timeseries"
    request = {
        "variable": [cds_variable],
        "location": {
            "longitude": GRID_RHINE_POINT[1],  # 8.0
            "latitude": GRID_RHINE_POINT[0],  # 47.5
        },
        "date": [date_range],
        "data_format": "netcdf",
    }

    try:
        client = cdsapi.Client()
        # Write directly to the target NetCDF path
        client.retrieve(dataset, request, target=output_file)

        logger.info(f"Successfully downloaded ERA5 data to {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"Failed to download ERA5 data: {e}")
        raise


def generate_date_range(start_date: str, end_date: str) -> str:
    """
    Generate date range string for CDS API.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Date range string for CDS API
    """
    return f"{start_date}/{end_date}"


def main():
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
        "--output-dir",
        default=RAW_ERA5_DIR,
        help="Output directory (default: data/raw/era5)",
    )

    args = parser.parse_args()

    logger.info("Starting ERA5 data download")
    logger.info(f"Variable: {args.variable}")
    logger.info(f"Date range: {args.start_date} to {args.end_date}")
    logger.info(f"Output directory: {args.output_dir}")

    try:
        downloaded_file = download_era5_data(
            args.variable, args.start_date, args.end_date, args.output_dir
        )
        logger.info(f"ERA5 download completed successfully: {downloaded_file}")

    except Exception as e:
        logger.error(f"ERA5 download failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
