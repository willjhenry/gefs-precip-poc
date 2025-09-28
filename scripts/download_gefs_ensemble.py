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

from hydro.common import RHINE_POINT

# Configuration
GEFS_BUCKET = "noaa-gefs-pds"
FORECAST_MODEL = "atmos/pgrb2sp25"
CYCLE = "00"  # 00z cycle only
FORECAST_HOURS = list(range(120, 169, 3))  # 120, 123, 126, ..., 168
ENSEMBLE_MEMBERS = (
    ["c00"]  # Control member
    + [f"gep{i:02d}" for i in range(1, 31)]  # 30 perturbed members
    + ["gespr", "geavg"]  # Spread and mean
)

# Paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INTERIM_GEFS_DIR = os.path.join(DATA_DIR, "interim", "gefs")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

LOG_FILE = os.path.join(SCRIPTS_DIR, "gefs_download.log")
CHECKPOINT_FILE = os.path.join(SCRIPTS_DIR, "gefs_checkpoint.json")
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "gefs_ensemble_tp.csv")


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
    # Correct filename pattern: {member}.t{CYCLE}z.pgrb2s.0p25.f{hour:03d}
    filename = f"{member}.t{CYCLE}z.pgrb2s.0p25.f{hour:03d}"
    s3_key = f"gefs.{date}/{CYCLE}/{FORECAST_MODEL}/{filename}"

    local_file = os.path.join(INTERIM_GEFS_DIR, filename)

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


def cleanup_index_files(filename: str) -> None:
    """
    Clean up any .idx index files created by cfgrib.

    Args:
        filename: Base GRIB2 filename (without .idx extension)
    """
    try:
        # cfgrib typically creates .idx files with the same base name
        idx_filename = f"{filename}.idx"
        if os.path.exists(idx_filename):
            os.remove(idx_filename)
            logging.debug(f"Removed index file: {idx_filename}")

        # Also check for any other potential index files
        for suffix in [".5b7b6.idx", ".idx"]:  # Common cfgrib index suffixes
            potential_idx = f"{filename}{suffix}"
            if os.path.exists(potential_idx):
                os.remove(potential_idx)
                logging.debug(f"Removed index file: {potential_idx}")

    except Exception as e:
        logging.debug(f"Could not clean up index files for {filename}: {e}")


def save_result_to_csv(result: dict, output_file: str = OUTPUT_FILE) -> None:
    """
    Append a single result to the CSV file.

    Args:
        result: Dictionary with result data
        output_file: Path to output CSV file
    """
    df = pd.DataFrame([result])
    # Append mode, no header if file exists
    file_exists = os.path.exists(output_file)
    df.to_csv(output_file, mode="a", header=not file_exists, index=False)


def process_date_member_hour(
    date: str, member: str, hour: int, output_file: str = OUTPUT_FILE
) -> bool:
    """
    Process a single date/member/hour combination.

    Args:
        date: Date in YYYYMMDD format
        member: Ensemble member
        hour: Forecast hour
        output_file: Path to output CSV file

    Returns:
        bool: True if successful, False if failed
    """
    success = False
    filename = None
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
        save_result_to_csv(result, output_file)

        logging.info(
            f"Processed: {date} {member} f{hour:03d} -> tp={tp_value:.4f}"
        )

        success = True

    except Exception as e:
        logging.warning(
            f"Failed to process {date} {member} f{hour:03d}: {e} - Skipping"
        )
        success = False

    # Clean up
    if filename:
        try:
            os.remove(filename)
        except Exception as e:
            logging.debug(f"Could not clean up {filename}: {e}")
        # Clean up any index files created by cfgrib
        cleanup_index_files(filename)
    return success


def get_valid_time(date_str: str, hour: int) -> str:
    """Calculate the valid time for a forecast."""
    date = datetime.strptime(date_str, "%Y%m%d")
    valid_time = date + timedelta(hours=hour)
    return valid_time.strftime("%Y-%m-%d %H:%M:%S")


def generate_date_range(
    start_date: str, end_date: str, test: bool = False
) -> List[str]:
    """Generate list of dates between start and end (inclusive)."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    if test:
        dates = dates[:1]
    return dates


def process_data(
    dates: List[str],
    ensemble_members: List[str],
    checkpoint: Optional[Tuple[str, str, int]],
):
    logger.info(f"Processing {len(dates)} dates: {dates[0]} to {dates[-1]}")
    start_processing = False
    for date in dates:
        logger.info(f"Processing date: {date}")

        for member in ensemble_members:
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

                # Process the file (gracefully handles failures)
                success = process_date_member_hour(
                    date, member, hour, OUTPUT_FILE
                )

                if success:
                    save_checkpoint(date, member, hour)


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


def get_ensemble_members(args: argparse.Namespace):
    if args.test:
        # Test mode: just one date, first few members
        ensemble_members = [
            "c00",
            "gep01",
            "gep02",
            "gespr",
            "geavg",
        ]  # Limited test set
        logger.info("TEST MODE: Processing 1 date with limited members")
    else:
        ensemble_members = ENSEMBLE_MEMBERS
    return ensemble_members


def main():
    args = parse_args()

    # Ensure required directories exist
    os.makedirs(INTERIM_GEFS_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # Generate date range
    dates = generate_date_range(args.start_date, args.end_date, args.test)

    # Get members to process
    ensemble_members = get_ensemble_members(args)

    # Load checkpoint if resuming
    checkpoint = load_checkpoint() if args.resume else None

    # If output file exists, mv it to a backup file with timestamp
    if os.path.exists(OUTPUT_FILE):
        backup_file = (
            f"{OUTPUT_FILE}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.rename(OUTPUT_FILE, backup_file)
        logger.info(f"Moved existing output file to {backup_file}")

    # Process data
    process_data(dates, ensemble_members, checkpoint)

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        logger.info("Removed checkpoint file")


if __name__ == "__main__":
    main()
