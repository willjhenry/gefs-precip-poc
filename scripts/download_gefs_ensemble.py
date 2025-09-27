#!/usr/bin/env python3
"""
AWS GEFS Ensemble Precipitation Data Downloader

Downloads GEFS ensemble precipitation data for Rhine basin point location.
Processes 30 perturbed members + control + spread + mean for 5-7 day forecasts.
Sequential processing with resume capability and memory-efficient operation.

Usage:
    python download_gefs_ensemble.py --start-date 2024-01-01 --end-date 2024-01-31
    python download_gefs_ensemble.py --resume  # Resume from checkpoint
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import boto3
import pandas as pd
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config

# Configuration
GEFS_BUCKET = "noaa-gefs-pds"
FORECAST_MODEL = "atmos/pgrb2sp25"
CYCLE = "00"  # 00z cycle only
RHINE_POINT = (47.5565597, 8.0483)  # Rhine basin point coordinates
FORECAST_HOURS = list(range(120, 169, 3))  # 120, 123, 126, ..., 168
ENSEMBLE_MEMBERS = (
    ["c00"]  # Control member
    + [f"p{i:02d}" for i in range(1, 31)]  # 30 perturbed members
    + ["gespr", "geavg"]  # Spread and mean
)

# Checkpoint file
CHECKPOINT_FILE = "gefs_checkpoint.json"
OUTPUT_FILE = "gefs_ensemble_tp.csv"


def setup_logging() -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("gefs_download.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def load_checkpoint() -> Optional[Tuple[str, str, int]]:
    """Load checkpoint from JSON file."""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                checkpoint = json.load(f)
            return (
                checkpoint["last_date"],
                checkpoint["last_member"],
                checkpoint["last_hour"],
            )
        except (json.JSONDecodeError, KeyError):
            logging.warning("Invalid checkpoint file, starting from beginning")
    return None


def save_checkpoint(date: str, member: str, hour: int) -> None:
    """Save current progress to checkpoint file."""
    checkpoint = {
        "last_date": date,
        "last_member": member,
        "last_hour": hour,
        "timestamp": datetime.now().isoformat(),
    }
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)


def download_gefs_file(date: str, member: str, hour: int) -> str:
    """
    Download a single GEFS file.

    Args:
        date: Date in YYYYMMDD format
        member: Ensemble member (c00, p01-p30, gespr, geavg)
        hour: Forecast hour

    Returns:
        Local filename
    """
    filename = f"gefs.t{CYCLE}z.{member}.0p25.f{hour:03d}"
    s3_key = f"gefs.{date}/{CYCLE}/{FORECAST_MODEL}/{filename}"

    local_file = filename

    # Download file
    s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    try:
        s3_client.download_file(GEFS_BUCKET, s3_key, local_file)
        logging.info(f"Downloaded: {filename}")
        return local_file
    except Exception as e:
        logging.error(f"Failed to download {filename}: {e}")
        raise


def extract_tp_value(filename: str) -> float:
    """
    Extract total precipitation value at Rhine point from GRIB2 file.

    Args:
        filename: Local GRIB2 filename

    Returns:
        tp value at Rhine point
    """
    try:
        # Load with cfgrib
        ds = xr.open_dataset(
            filename,
            engine="cfgrib",
            filter_by_keys={"typeOfLevel": "surface", "stepType": "accum"},
        )

        # Select Rhine point
        rhine_data = ds.sel(
            latitude=RHINE_POINT[0], longitude=RHINE_POINT[1], method="nearest"
        )

        # Get tp value
        tp_value = float(rhine_data["tp"].values)

        return tp_value

    except Exception as e:
        logging.error(f"Failed to extract tp from {filename}: {e}")
        raise


def process_date_member_hour(
    date: str, member: str, hour: int, results: List[dict]
) -> None:
    """
    Process a single date/member/hour combination.

    Args:
        date: Date in YYYYMMDD format
        member: Ensemble member
        hour: Forecast hour
        results: List to append results to
    """
    try:
        # Download file
        filename = download_gefs_file(date, member, hour)

        # Extract tp value
        tp_value = extract_tp_value(filename)

        # Record result
        result = {
            "forecast_date": date,
            "ensemble_member": member,
            "forecast_hour": hour,
            "tp_value": tp_value,
            "valid_time": get_valid_time(date, hour),
        }
        results.append(result)

        # Clean up
        os.remove(filename)
        logging.info(
            f"Processed: {date} {member} f{hour:03d} -> tp={tp_value:.4f}"
        )

    except Exception as e:
        logging.error(f"Failed to process {date} {member} f{hour:03d}: {e}")
        raise


def get_valid_time(date_str: str, hour: int) -> str:
    """Calculate the valid time for a forecast."""
    date = datetime.strptime(date_str, "%Y%m%d")
    valid_time = date + timedelta(hours=hour)
    return valid_time.strftime("%Y-%m-%d %H:%M:%S")


def generate_date_range(start_date: str, end_date: str) -> List[str]:
    """Generate list of dates between start and end (inclusive)."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    return dates


def main():
    """Main execution function."""
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
        "--output", default=OUTPUT_FILE, help="Output CSV file"
    )

    args = parser.parse_args()

    logger = setup_logging()
    logger.info("Starting GEFS ensemble data download")

    # Generate date range
    dates = generate_date_range(args.start_date, args.end_date)
    logger.info(
        f"Processing {len(dates)} dates: {args.start_date} to {args.end_date}"
    )

    # Load checkpoint if resuming
    checkpoint = load_checkpoint() if args.resume else None

    # Initialize results
    results = []
    start_processing = False

    # Main processing loop
    for date in dates:
        logger.info(f"Processing date: {date}")

        for member in ENSEMBLE_MEMBERS:
            for hour in FORECAST_HOURS:
                # Check if we should start processing (for resume)
                if checkpoint:
                    if (
                        date < checkpoint[0]
                        or (date == checkpoint[0] and member < checkpoint[1])
                        or (
                            date == checkpoint[0]
                            and member == checkpoint[1]
                            and hour <= checkpoint[2]
                        )
                    ):
                        continue
                    start_processing = True

                if not start_processing and not checkpoint:
                    start_processing = True

                if not start_processing:
                    continue

                try:
                    process_date_member_hour(date, member, hour, results)
                    save_checkpoint(date, member, hour)

                except Exception as e:
                    logger.error(f"Failed on {date} {member} f{hour:03d}: {e}")
                    # Continue with next item rather than stopping
                    continue

    # Save results to CSV
    if results:
        df = pd.DataFrame(results)
        df.to_csv(args.output, index=False)
        logger.info(f"Saved {len(results)} records to {args.output}")
    else:
        logger.warning("No data was processed successfully")

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        logger.info("Removed checkpoint file")


if __name__ == "__main__":
    main()
