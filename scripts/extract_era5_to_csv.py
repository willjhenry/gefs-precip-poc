"""
Extract ERA5 NetCDF files to CSVs at Rhine grid point (47.5N, 8.0E).

Scans data/raw/era5/ for .nc files, uses NetCDFDataExtractor to pull time series,
and saves per-file CSVs to data/processed/ with grid point in filename.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
from typing import List

from hydro.common import (
    GRID_RHINE_POINT,
    PROCESSED_DIR,
    RAW_ERA5_DIR,
    SCRIPTS_DIR,
)
from hydro.data_processors.netcdf_extractor import NetCDFDataExtractor

# Setup paths (mirror other scripts)
LOG_FILE = os.path.join(SCRIPTS_DIR, "era5_extract.log")


def setup_logging(log_file: str) -> logging.Logger:
    """Configure logger for file and console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def find_era5_files(raw_dir: str) -> List[str]:
    """Find all .nc files in raw_dir."""
    pattern = os.path.join(raw_dir, "era5_*.nc")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No ERA5 .nc files found in {raw_dir}")
    return sorted(files)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract ERA5 NetCDFs to CSVs at grid point (47.5N, 8.0E)",
    )
    parser.add_argument(
        "--raw-dir",
        default=RAW_ERA5_DIR,
        help="Directory containing ERA5 .nc files",
    )
    parser.add_argument(
        "--processed-dir",
        default=PROCESSED_DIR,
        help="Output directory for CSVs",
    )
    parser.add_argument(
        "--variables",
        nargs="+",
        default=["tp", "t2m"],
        help="Variables to extract (e.g., tp t2m)",
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=GRID_RHINE_POINT[0],
        help="Latitude for extraction",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=GRID_RHINE_POINT[1],
        help="Longitude for extraction",
    )
    args = parser.parse_args()

    logger = setup_logging(LOG_FILE)
    os.makedirs(args.processed_dir, exist_ok=True)

    # Process each variable separately
    for var in args.variables:
        logger.info(
            f"Processing variable '{var}' at lat={args.lat}, lon={args.lon}"
        )
        extractor = NetCDFDataExtractor(
            lat=args.lat,
            lon=args.lon,
            variable=var,
        )

        files = find_era5_files(args.raw_dir)
        logger.info(f"Found {len(files)} .nc files for {var}")

        for file_path in files:
            # Infer if file matches variable (e.g., era5_tp_*.nc)
            base = os.path.basename(file_path)
            if var not in base:
                logger.warning(
                    f"Skipping {base} (doesn't match variable '{var}')"
                )
                continue

            try:
                output_csv = extractor.extract_to_csv(
                    file_path=file_path,
                    output_dir=args.processed_dir,
                )
                logger.info(f"Completed: {output_csv}")
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")

    logger.info("Extraction complete. Check data/processed/ for CSVs.")


if __name__ == "__main__":
    main()
