"""
Extract a single ERA5 NetCDF file to a CSV at a grid point.

Given an input `.nc` file, this script uses NetCDFDataExtractor to pull the
time series at a target lat/lon and writes a CSV into the structured
processed directory: data/processed/era5/<grid>/<variable>/hourly/.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from typing import Literal

from hydro.common import (
    SCRIPTS_DIR,
    build_era5_processed_dir,
)
from hydro.data_processors.netcdf_extractor import NetCDFDataExtractor

# Setup paths (mirror other scripts)
LOG_FILE = os.path.join(SCRIPTS_DIR, "era5_extract.log")


"""Configure logger for file and console."""
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def determine_variable(base: str) -> Literal["tp", "t2m"]:
    if "_tp_" in base:
        var = "tp"
    elif "_t2m_" in base:
        var = "t2m"
    else:
        raise ValueError(
            "Could not infer variable from filename. Provide --variable (tp or t2m)."
        )
    return var


def determine_location(base: str) -> tuple[float, float]:
    m = re.search(r"lat-([0-9p-]+)_lon-([0-9p-]+)", base)
    if m:
        lat_str, lon_str = m.groups()
        lat = float(lat_str.replace("p", "."))
        lon = float(lon_str.replace("p", "."))
    else:
        raise ValueError(
            "Could not infer location from filename. Provide --lat and --lon."
        )
    return lat, lon


def parse_args() -> tuple[str, Literal["tp", "t2m"], float, float]:
    parser = argparse.ArgumentParser(
        description="Extract a single ERA5 NetCDF to CSV at a grid point",
    )
    parser.add_argument(
        "input_nc",
        help="Path to ERA5 NetCDF (.nc) file",
    )
    args = parser.parse_args()

    input_nc = args.input_nc
    if not os.path.isfile(input_nc):
        raise FileNotFoundError(f"Input NetCDF not found: {input_nc}")

    base = os.path.basename(input_nc)
    var = determine_variable(base)
    lat, lon = determine_location(base)
    return input_nc, var, lat, lon


def main() -> None:
    input_nc, var, lat, lon = parse_args()
    logger.info(f"Processing {input_nc} | var={var} | lat={lat} lon={lon}")

    # Compute structured output directory
    output_dir = build_era5_processed_dir((lat, lon), var, "hourly")
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    extractor = NetCDFDataExtractor(
        lat=lat,
        lon=lon,
        variable=var,
    )

    try:
        output_csv = extractor.extract_to_csv(
            file_path=input_nc,
            output_dir=output_dir,
        )
        logger.info(f"Completed: {output_csv}")
    except Exception as e:
        logger.error(f"Failed to process {input_nc}: {e}")


if __name__ == "__main__":
    main()
