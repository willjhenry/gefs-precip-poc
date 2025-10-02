"""Shared constants for the Hydro POC project."""

from __future__ import annotations

import os
from typing import Literal, Tuple

import pandas as pd

RHINE_POINT = (47.5565597, 8.0483)
GRID_RHINE_POINT = (47.5, 8.0)

# Project paths (computed relative to this file's location)
PROJECT_ROOT: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
MODEL_ARTIFACTS_DIR: str = os.path.join(PROJECT_ROOT, "model_artifacts")
SCRIPTS_DIR: str = os.path.join(PROJECT_ROOT, "scripts")
DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
RAW_ERA5_DIR: str = os.path.join(DATA_DIR, "raw", "era5")

INTERIM_GEFS_DIR = os.path.join(DATA_DIR, "interim", "gefs")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
PROCESSED_GEFS_DIR = os.path.join(PROCESSED_DIR, "gefs")
PROCESSED_ERA5_DIR = os.path.join(PROCESSED_DIR, "era5")


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


def grid_tags(lat: float, lon: float) -> str:
    """
    Return shell-friendly grid tags as 'lat-47p5_lon-8p0'.

    Parameters
    ----------
    lat : float
        Latitude.
    lon : float
        Longitude.

    Returns
    -------
    str
        Shell-friendly grid tag.
    """
    return f"lat-{_format_coord_component(lat)}_lon-{_format_coord_component(lon)}"


def build_gefs_processed_dir(
    location: Tuple[float, float],
    lead_start: int,
    lead_end: int,
) -> str:
    """
    Build GEFS processed directory: data/processed/gefs/<grid>/lead_<start>-<end>/

    Parameters
    ----------
    location : Tuple[float, float]
        Latitude and longitude.
    lead_start : int
        Start of lead time window (hours).
    lead_end : int
        End of lead time window (hours).

    Returns
    -------
    str
        Path to GEFS processed directory.
    """
    lat, lon = location
    return os.path.join(
        PROCESSED_GEFS_DIR,
        grid_tags(lat, lon),
        f"lead_{lead_start}-{lead_end}",
    )


def build_gefs_basename(
    kind: Literal["freq-3h", "sum"],
    location: Tuple[float, float],
    lead_start: int,
    lead_end: int,
    cycle: str,
) -> str:
    """
    Basename for GEFS files (no date range or extension).

    Parameters
    ----------
    kind : Literal["freq-3h", "sum"]
        Type of GEFS file.
    location : Tuple[float, float]
        Latitude and longitude.
    lead_start : int
        Start of lead time window (hours).
    lead_end : int
        End of lead time window (hours).
    cycle : str
        Cycle string (e.g., "00").

    Returns
    -------
    str
        Basename for GEFS file.

    Examples
    --------
    gefs_tp_freq-3h_lat-47p5_lon-8p0_lead-120-168_cycle-00z
    gefs_tp_sum_lat-47p5_lon-8p0_lead-120-168_cycle-00z
    """
    lat, lon = location
    return (
        f"gefs_tp_{kind}_"
        f"{grid_tags(lat, lon)}_"
        f"lead-{lead_start}-{lead_end}_"
        f"cycle-{cycle}z"
    )


def finalize_csv_with_date_range(csv_path: str, date_col: str) -> str:
    """
    Append YYYYMMDD-YYYYMMDD to csv_path based on min/max of date_col.

    Parameters
    ----------
    csv_path : str
        Path to the CSV to finalize.
    date_col : str
        Column that contains datetimes to compute the range.

    Returns
    -------
    str
        Final path after renaming (may be unchanged).
    """
    df = pd.read_csv(csv_path, usecols=[date_col], parse_dates=[date_col])
    if df.empty or df[date_col].isna().all():
        return csv_path
    start = df[date_col].min().strftime("%Y%m%d")
    end = df[date_col].max().strftime("%Y%m%d")
    base, ext = os.path.splitext(csv_path)
    final_path = f"{base}_{start}-{end}{ext}"
    if final_path != csv_path:
        os.rename(csv_path, final_path)
    return final_path


def build_era5_processed_dir(
    location: Tuple[float, float],
    variable: Literal["tp", "t2m"],
    frequency: Literal["hourly", "daily"],
) -> str:
    """
    Build ERA5 processed directory: data/processed/era5/<grid>/<variable>/<frequency>/

    Parameters
    ----------
    location : Tuple[float, float]
        Latitude and longitude.
    variable : Literal["tp", "t2m"]
        Variable name.
    frequency : Literal["hourly", "daily"]
        Frequency of data.

    Returns
    -------
    str
        Path to ERA5 processed directory.
    """
    lat, lon = location
    return os.path.join(
        PROCESSED_ERA5_DIR, grid_tags(lat, lon), variable, frequency
    )


def build_era5_basename(
    variable: Literal["tp", "t2m"],
    frequency: Literal["hourly", "daily"],
    location: Tuple[float, float],
) -> str:
    """
    Basename for ERA5 files (no date range or extension).

    Parameters
    ----------
    variable : Literal["tp", "t2m"]
        Variable name.
    frequency : Literal["hourly", "daily"]
        Frequency of data.
    location : Tuple[float, float]
        Latitude and longitude.

    Returns
    -------
    str
        Basename for ERA5 file.

    Examples
    --------
    era5_tp_freq-1h_lat-47p5_lon-8p0
    era5_tp_daily_lat-47p5_lon-8p0
    """
    lat, lon = location
    if frequency == "hourly":
        return f"era5_{variable}_freq-1h_{grid_tags(lat, lon)}"
    elif frequency == "daily":
        return f"era5_{variable}_freq-1d_{grid_tags(lat, lon)}"
    else:
        raise ValueError(f"Invalid frequency: {frequency}")
