"""Shared constants for the Hydro POC project."""

import os

RHINE_POINT = (47.5565597, 8.0483)
GRID_RHINE_POINT = (47.5, 8.0)

# Project paths (computed relative to this file's location)
PROJECT_ROOT: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
SCRIPTS_DIR: str = os.path.join(PROJECT_ROOT, "scripts")
DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
RAW_ERA5_DIR: str = os.path.join(DATA_DIR, "raw", "era5")

INTERIM_GEFS_DIR = os.path.join(DATA_DIR, "interim", "gefs")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")


def _format_coord_component(value: float) -> str:
    """Format a coordinate as signed integer with 'p' as decimal separator.

    Examples
    --------
    47.5 -> '47p5'
    8.0 -> '8p0'
    -7.5 -> '-7p5'
    """
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    integer_part = int(abs_val)
    tenths = int(round((abs_val - integer_part) * 10))
    return f"{sign}{integer_part}p{tenths}"


def grid_point_string(lat: float, lon: float) -> str:
    """Return grid point string in the form '(47p5,8p0)'."""
    return f"({_format_coord_component(lat)},{_format_coord_component(lon)})"
