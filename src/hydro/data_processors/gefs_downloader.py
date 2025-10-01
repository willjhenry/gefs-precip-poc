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
    - Extracted CSV is saved to structured directory: `data/processed/gefs/lat-<lat>_lon-<lon>/lead_<start>-<end>/`
    - Log and checkpoint files are stored in the `scripts/` directory
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import boto3
import pandas as pd
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config

from hydro.common import (
    INTERIM_GEFS_DIR,
    PROCESSED_DIR,
    SCRIPTS_DIR,
    build_gefs_basename,
    build_gefs_processed_dir,
    finalize_csv_with_date_range,
    grid_point_string,
)

# Paths


class GEFSDownloader:
    """
    Download GEFS ensemble precipitation data for Rhine basin point location.
    """

    # Configuration
    GEFS_BUCKET = "noaa-gefs-pds"
    FORECAST_MODEL = "atmos/pgrb2sp25"
    CYCLE = "00"  # 00z cycle only
    FORECAST_HOURS = list(range(120, 169, 3))  # 120, 123, 126, ..., 168
    ENSEMBLE_MEMBERS = (
        ["gec00"]  # Control member
        + [f"gep{i:02d}" for i in range(1, 31)]  # 30 perturbed members
        + ["gespr", "geavg"]  # Spread and mean
    )
    TEST_ENSEMBLE_MEMBERS = ["gec00", "gep01", "gep02", "gespr", "geavg"]

    def __init__(
        self,
        start_date: str,
        end_date: str,
        location: Tuple[float, float],
        cycle: Optional[str] = None,
        forecast_hours: Optional[List[int]] = None,
        ensemble_members: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
        test: bool = False,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.location = location
        self.cycle = cycle or self.CYCLE
        self.forecast_hours = forecast_hours or self.FORECAST_HOURS.copy()
        self.ensemble_members = (
            ensemble_members or self.ENSEMBLE_MEMBERS.copy()
        )
        self.test = test

        self.interim_gefs_dir = INTERIM_GEFS_DIR
        self.processed_dir = PROCESSED_DIR

        # Compute lead time bounds
        self.lead_start = min(self.forecast_hours)
        self.lead_end = max(self.forecast_hours)

        # Build new directory structure and filename
        gefs_dir = build_gefs_processed_dir(
            self.location, self.lead_start, self.lead_end
        )
        basename = build_gefs_basename(
            kind="freq-3h",
            location=self.location,
            lead_start=self.lead_start,
            lead_end=self.lead_end,
            cycle=self.cycle,
        )
        self.output_file = os.path.join(gefs_dir, f"{basename}.csv")

        # Create standardized grid point string like '(47p5,8p0)' for checkpoint
        location_str = grid_point_string(self.location[0], self.location[1])
        self.checkpoint_file = os.path.join(
            SCRIPTS_DIR,
            f"gefs_checkpoint_{location_str}.json",
        )

        self.logger = logger or logging.getLogger(__name__)

        self._set_dates()

        if self.test:
            self.logger.info(
                "TEST MODE: Processing up to 2 dates with limited members"
            )
            self.ensemble_members = self.TEST_ENSEMBLE_MEMBERS
            self.dates = self.dates[:2]

    def _set_dates(self) -> None:
        """Generate list of dates between start and end (inclusive)."""
        start = datetime.strptime(self.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.end_date, "%Y-%m-%d")

        if end < start:
            self.logger.error("End date is before start date")
            raise ValueError("End date is before start date")

        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)

        self.dates = dates

    def download(
        self,
        resume: bool = False,
    ):
        self.logger.info(
            f"Processing {len(self.dates)} dates: {self.dates[0]} to {self.dates[-1]}"
        )

        # Ensure interim gefs dir and processed dir exist
        os.makedirs(self.interim_gefs_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)

        # Ensure the specific GEFS output directory exists
        gefs_dir = os.path.dirname(self.output_file)
        os.makedirs(gefs_dir, exist_ok=True)

        # Check if output file exists, backup if it does
        if os.path.exists(self.output_file):
            backup_file = f"{self.output_file}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(self.output_file, backup_file)
            self.logger.info(f"Moved existing output file to {backup_file}")

        checkpoint = self._load_checkpoint() if resume else None

        start_processing = False
        for date in self.dates:
            self.logger.info(f"Processing date: {date}")

            for member in self.ensemble_members:
                for hour in self.forecast_hours:
                    # Check if we should start processing (for resume)
                    if checkpoint:
                        if (
                            date < checkpoint[0]
                            or (
                                date == checkpoint[0]
                                and member < checkpoint[1]
                            )
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
                    success = self._process_date_member_hour(
                        date, member, hour
                    )

                    if success:
                        self._save_checkpoint(date, member, hour)

        # Clean up checkpoint
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
            self.logger.info("Removed checkpoint file")

        # Finalize CSV with date range
        self.output_file = finalize_csv_with_date_range(
            self.output_file, date_col="valid_time"
        )
        self.logger.info(f"Finalized output file: {self.output_file}")

    def _process_date_member_hour(
        self, date: str, member: str, hour: int
    ) -> bool:
        """
        Process a single date/member/hour combination.

        Args:
            date: Date in YYYYMMDD format
            member: Ensemble member
            hour: Forecast hour

        Returns:
            bool: True if successful, False if failed
        """
        success = False
        filename = None
        try:
            # Download file
            filename = self._download_gefs_file(date, member, hour)

            # Extract tp value
            tp = self._extract_tp(filename)

            # Record result
            result = {
                "forecast_date": date,
                "ensemble_member": member,
                "forecast_hour": hour,
                "tp": tp,
                "valid_time": self._get_valid_time(date, hour),
            }
            self._save_result_to_csv(result)

            self.logger.info(
                f"Processed: {date} {member} f{hour:03d} -> tp={tp:.4f}"
            )

            success = True

        except Exception as e:
            self.logger.warning(
                f"Failed to process {date} {member} f{hour:03d}: {e} - Skipping"
            )
            success = False

        # Clean up
        if filename:
            try:
                os.remove(filename)
            except Exception as e:
                self.logger.debug(f"Could not clean up {filename}: {e}")
            # Clean up any index files created by cfgrib
            self._cleanup_index_files(filename)
        return success

    def _download_gefs_file(self, date: str, member: str, hour: int) -> str:
        """
        Download a single GEFS file.

        Args:
            date: Date in YYYYMMDD format
            member: Ensemble member (c00, p01-p30, gespr, geavg)
            hour: Forecast hour

        Returns:
            Local filename
        """
        filename = f"{member}.t{self.cycle}z.pgrb2s.0p25.f{hour:03d}"
        s3_key = f"gefs.{date}/{self.cycle}/{self.FORECAST_MODEL}/{filename}"

        local_file = os.path.join(self.interim_gefs_dir, filename)

        # Download file
        s3_client = boto3.client(
            "s3", config=Config(signature_version=UNSIGNED)
        )
        try:
            s3_client.download_file(self.GEFS_BUCKET, s3_key, local_file)
            self.logger.info(f"Downloaded: {filename}")
            return local_file
        except Exception as e:
            self.logger.error(f"Failed to download {filename}: {e}")
            raise

    def _extract_tp(self, filename: str) -> float:
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
                latitude=self.location[0],
                longitude=self.location[1],
                method="nearest",
            )

            # Get tp value
            tp = float(rhine_data["tp"].values)

            return tp

        except Exception as e:
            self.logger.error(f"Failed to extract tp from {filename}: {e}")
            raise

    def _cleanup_index_files(self, filename: str) -> None:
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
                self.logger.debug(f"Removed index file: {idx_filename}")

            # Also check for any other potential index files
            for suffix in [
                ".5b7b6.idx",
                ".idx",
            ]:  # Common cfgrib index suffixes
                potential_idx = f"{filename}{suffix}"
                if os.path.exists(potential_idx):
                    os.remove(potential_idx)
                    self.logger.debug(f"Removed index file: {potential_idx}")

        except Exception as e:
            self.logger.debug(
                f"Could not clean up index files for {filename}: {e}"
            )

    def _load_checkpoint(self) -> Optional[Tuple[str, str, int]]:
        """Load checkpoint from JSON file."""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                return (
                    checkpoint["last_date"],
                    checkpoint["last_member"],
                    checkpoint["last_hour"],
                )
            except (json.JSONDecodeError, KeyError):
                self.logger.warning(
                    "Invalid checkpoint file, starting from beginning"
                )
        return None

    def _save_checkpoint(self, date: str, member: str, hour: int) -> None:
        """Save current progress to checkpoint file."""
        checkpoint = {
            "last_date": date,
            "last_member": member,
            "last_hour": hour,
            "timestamp": datetime.now().isoformat(),
        }
        with open(self.checkpoint_file, "w") as f:
            json.dump(checkpoint, f, indent=2)

    def _save_result_to_csv(self, result: dict) -> None:
        """
        Append a single result to the CSV file.

        Args:
            result: Dictionary with result data
        """
        df = pd.DataFrame([result])
        # Append mode, no header if file exists
        file_exists = os.path.exists(self.output_file)
        df.to_csv(
            self.output_file, mode="a", header=not file_exists, index=False
        )

    def _get_valid_time(self, date_str: str, hour: int) -> str:
        """Calculate the valid time for a forecast."""
        date = datetime.strptime(date_str, "%Y%m%d")
        valid_time = date + timedelta(hours=hour)
        return valid_time.strftime("%Y-%m-%d %H:%M:%S")
