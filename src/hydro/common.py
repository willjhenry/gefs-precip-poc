"""Shared constants for the Hydro POC project."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Literal, Optional, Tuple

import boto3
import pandas as pd
from botocore import UNSIGNED
from botocore.config import Config

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
RESULTS_DIR: str = os.path.join(PROJECT_ROOT, "results")
PREDICTIONS_DIR: str = os.path.join(RESULTS_DIR, "predictions")

INTERIM_GEFS_DIR = os.path.join(DATA_DIR, "interim", "gefs")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
PROCESSED_GEFS_DIR = os.path.join(PROCESSED_DIR, "gefs")
PROCESSED_ERA5_DIR = os.path.join(PROCESSED_DIR, "era5")


def find_latest_meta_under_tag_dirs(base_dir: str) -> Optional[str]:
    """Return newest meta file path under model_artifacts/<tag>/.

    Expects artifacts to be organized as::

        model_artifacts/<tag>/meta_<tag>.json

    Parameters
    ----------
    base_dir : str
        Path to the `model_artifacts` directory.

    Returns
    -------
    Optional[str]
        Path to the newest `meta_<tag>.json` found, or None if none exist.
    """
    newest_path: Optional[str] = None
    newest_mtime: float = -1.0
    try:
        subdirs = [
            d
            for d in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, d))
        ]
    except FileNotFoundError:
        return None
    for tag in subdirs:
        meta_path = os.path.join(base_dir, tag, f"meta_{tag}.json")
        if os.path.exists(meta_path):
            try:
                mtime = os.path.getmtime(meta_path)
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_path = meta_path
    return newest_path


def tag_from_meta_path(meta_path: str) -> Optional[str]:
    """Extract tag from a meta file path like ``.../meta_<tag>.json``.

    Parameters
    ----------
    meta_path : str
        Path to the meta JSON file.

    Returns
    -------
    Optional[str]
        The extracted tag or None if it cannot be parsed.
    """
    m = re.search(r"meta_(.+)\.json$", os.path.basename(meta_path))
    return m.group(1) if m else None


def align_columns(
    df: pd.DataFrame,
    required_cols: list[str],
    fill_value: float = 0.0,
    dtype: type = float,
) -> pd.DataFrame:
    """Ensure a DataFrame contains required columns with numeric dtype.

    For any missing column in ``required_cols``, this function creates it and
    fills with ``fill_value``. All required columns are coerced to numeric and
    NaNs are filled with ``fill_value``. Columns not listed in ``required_cols``
    are left unchanged.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    required_cols : list[str]
        Column names that must be present.
    fill_value : float, optional
        Value to use for missing columns and NaNs (default 0.0).
    dtype : type, optional
        Target dtype for required columns (default float).

    Returns
    -------
    pd.DataFrame
        A DataFrame with at least the required columns present and numeric.
    """
    aligned = df.copy()
    for col in required_cols:
        if col not in aligned.columns:
            aligned[col] = fill_value
    # Coerce to numeric, fill NaNs, and ensure final dtype
    aligned[required_cols] = (
        aligned[required_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(fill_value)
        .astype(dtype)
    )
    return aligned


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


# ---------- Filename parsing helpers (standardized names) ----------


def parse_grid_from_name(filename: str) -> Optional[Tuple[float, float]]:
    """Parse grid (lat, lon) from standardized filename.

    Supports `lat-<latp>_lon-<lonp>` pattern used across GEFS/ERA5 outputs.

    Returns
    -------
    Optional[Tuple[float, float]]
        (lat, lon) in decimal degrees, or None if not found.
    """
    m = re.search(r"lat-([0-9p-]+)_lon-([0-9p-]+)", filename)
    if not m:
        return None
    lat_str, lon_str = m.groups()
    try:
        lat = float(lat_str.replace("p", "."))
        lon = float(lon_str.replace("p", "."))
        return (lat, lon)
    except Exception:
        return None


def parse_lead_range_from_name(filename: str) -> Optional[Tuple[int, int]]:
    """Parse lead hour range from filename, e.g., `lead-120-168`.

    Returns
    -------
    Optional[Tuple[int, int]]
        (start, end) if found, else None.
    """
    m = re.search(r"lead-(\d{2,3})-(\d{2,3})", filename)
    if not m:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)))
    except Exception:
        return None


def parse_cycle_from_name(filename: str) -> Optional[str]:
    """Parse cycle (e.g., `cycle-00z`) and return `00`.

    Returns
    -------
    Optional[str]
        Cycle string without trailing 'z' or None if not found.
    """
    m = re.search(r"cycle-(\d{2})z", filename)
    return m.group(1) if m else None


def parse_date_range_from_name(filename: str) -> Optional[Tuple[str, str]]:
    """Parse date range suffix `_YYYYMMDD-YYYYMMDD`.

    Returns
    -------
    Optional[Tuple[str, str]]
        (start, end) as strings if found, else None.
    """
    m = re.search(r"_(\d{8})-(\d{8})\.csv$", filename)
    if m:
        return (m.group(1), m.group(2))
    m = re.search(r"_(\d{8})_(\d{8})\.csv$", filename)
    if m:
        return (m.group(1), m.group(2))
    return None


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


def build_live_predictions_dir(
    model_tag: str,
    location: Tuple[float, float],
    lead_start: int,
    lead_end: int,
) -> str:
    """Build live predictions directory path.

    Returns a path of the form:

    results/predictions/live/<model_tag>/<grid>/lead_<start>-<end>/

    Parameters
    ----------
    model_tag : str
        Artifact tag identifying a model run.
    location : Tuple[float, float]
        Latitude and longitude of the grid point.
    lead_start : int
        Start of the lead window in hours.
    lead_end : int
        End of the lead window in hours.

    Returns
    -------
    str
        Directory path for live predictions output.
    """
    lat, lon = location
    return os.path.join(
        PREDICTIONS_DIR,
        "live",
        model_tag,
        grid_tags(lat, lon),
        f"lead_{lead_start}-{lead_end}",
    )


def build_live_prediction_filename(
    location: Tuple[float, float],
    lead_start: int,
    lead_end: int,
    cycle: str,
    timestamp_utc: str,
    fmt: str,
) -> str:
    """Build a live prediction filename.

    The filename follows:

    live_<timestampZ>_<grid>_lead-<start>-<end>_cycle-<cycle>z.<fmt>

    Parameters
    ----------
    location : Tuple[float, float]
        Latitude and longitude of the grid point.
    lead_start : int
        Start of the lead window in hours.
    lead_end : int
        End of the lead window in hours.
    cycle : str
        Cycle string (e.g., "00", "06").
    timestamp_utc : str
        UTC timestamp string (e.g., "YYYYMMDDTHHMMSSZ").
    fmt : str
        File extension to use (e.g., "csv", "json").

    Returns
    -------
    str
        Filename (not including directory path).
    """
    lat, lon = location
    return (
        f"live_{timestamp_utc}_{grid_tags(lat, lon)}_"
        f"lead-{lead_start}-{lead_end}_cycle-{cycle}z.{fmt}"
    )


def utc_timestamp() -> str:
    """Return current UTC time in YYYYMMDDTHHMMSSZ format."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_forecast_hours(start: int, end: int, step: int) -> list[int]:
    """Generate an inclusive range of forecast hours.

    Parameters
    ----------
    start : int
        Start hour (inclusive).
    end : int
        End hour (inclusive).
    step : int
        Step in hours.

    Returns
    -------
    list[int]
        Sequence of forecast hours.
    """
    return list(range(start, end + 1, step))


def s3_object_exists(bucket: str, key: str) -> bool:
    """Return True if an S3 object exists using unsigned access.

    Parameters
    ----------
    bucket : str
        S3 bucket name.
    key : str
        S3 object key.

    Returns
    -------
    bool
        True if the object exists, else False.
    """
    s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False
