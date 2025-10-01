## Data workflow structure and naming (GEFS + ERA5)

### Goals

- Standardize processed data directory layout for clarity and scalability.
- Adopt consistent, shell-friendly filenames encoding key metadata.
- Update code to write/read using the new structure, while tolerating legacy files.

---

### Directory structure

- GEFS (processed, organized by grid and lead window)

  - `data/processed/gefs/lat-47p5_lon-8p0/lead_120-168/`
    - Contains per-hour (3h) extraction and aggregated (sum) CSVs.

- ERA5 (processed, organized by grid, variable, and frequency)
  - `data/processed/era5/lat-47p5_lon-8p0/tp/hourly/`
  - `data/processed/era5/lat-47p5_lon-8p0/tp/daily/`
  - `data/processed/era5/lat-47p5_lon-8p0/t2m/hourly/`
  - `data/processed/era5/lat-47p5_lon-8p0/t2m/daily/`

Example tree:

```text
data/processed/
  gefs/
    lat-47p5_lon-8p0/
      lead_120-168/
  era5/
    lat-47p5_lon-8p0/
      tp/
        hourly/
        daily/
      t2m/
        hourly/
        daily/
```

Notes:

- Keep grid as two separate fields `lat-<val>_lon-<val>` for clear parsing.
- GEFS cycle remains in the filename, not as a directory.

---

### Filename conventions

General delimiter rules:

- Underscores separate fields; hyphens bind key→value pairs and ranges.
- Grid fields: `lat-47p5_lon-8p0`
- Date ranges: `YYYYMMDD-YYYYMMDD`
- GEFS dates use the valid-time range (not initialization times).

GEFS:

- Per-hour (3-hourly accumulations)
  - `gefs_tp_freq-3h_lat-47p5_lon-8p0_lead-120-168_cycle-00z_20230101-20250215.csv`
- Aggregated (sum over lead window)
  - `gefs_tp_sum_lat-47p5_lon-8p0_lead-120-168_cycle-00z_20230101-20250215.csv`

ERA5:

- Hourly (1-hourly)
  - `era5_tp_freq-1h_lat-47p5_lon-8p0_20230101-20250215.csv`
  - `era5_t2m_freq-1h_lat-47p5_lon-8p0_20230101-20250215.csv`
- Daily
  - `era5_tp_daily_lat-47p5_lon-8p0_20230101-20250215.csv`
  - `era5_t2m_daily_lat-47p5_lon-8p0_20230101-20250215.csv`

Patterns with placeholders:

- GEFS per-hour: `gefs_tp_freq-3h_lat-<lat>_lon-<lon>_lead-<start>-<end>_cycle-<cycle>_YYYYMMDD-YYYYMMDD.csv`
- GEFS sum: `gefs_tp_sum_lat-<lat>_lon-<lon>_lead-<start>-<end>_cycle-<cycle>_YYYYMMDD-YYYYMMDD.csv`
- ERA5 hourly: `era5_<var>_freq-1h_lat-<lat>_lon-<lon>_YYYYMMDD-YYYYMMDD.csv`
- ERA5 daily: `era5_<var>_daily_lat-<lat>_lon-<lon>_YYYYMMDD-YYYYMMDD.csv`

---

### Code changes

#### 1) Add path/naming helpers in `src/hydro/common.py`

```python
from __future__ import annotations

import os
from typing import Literal, Tuple

import pandas as pd

# Existing: PROJECT_ROOT, DATA_DIR, PROCESSED_DIR, _format_coord_component
PROCESSED_GEFS_DIR = os.path.join(PROCESSED_DIR, "gefs")
PROCESSED_ERA5_DIR = os.path.join(PROCESSED_DIR, "era5")


def grid_tags(lat: float, lon: float) -> str:
    """
    Return shell-friendly grid tags as 'lat-47p5_lon-8p0'.
    """
    return f"lat-{_format_coord_component(lat)}_lon-{_format_coord_component(lon)}"


def build_gefs_processed_dir(
    location: Tuple[float, float],
    lead_start: int,
    lead_end: int,
) -> str:
    """
    Build GEFS processed directory: data/processed/gefs/<grid>/lead_<start>-<end>/
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
    """
    lat, lon = location
    return os.path.join(PROCESSED_ERA5_DIR, grid_tags(lat, lon), variable, frequency)


def build_era5_basename(
    variable: Literal["tp", "t2m"],
    frequency: Literal["hourly", "daily"],
    location: Tuple[float, float],
) -> str:
    """
    Basename for ERA5 files (no date range or extension).
    """
    lat, lon = location
    if frequency == "hourly":
        return f"era5_{variable}_freq-1h_{grid_tags(lat, lon)}"
    return f"era5_{variable}_daily_{grid_tags(lat, lon)}"
```

#### 2) GEFS downloader: write per-hour CSV to new path and finalize with valid-time range

Edit `src/hydro/data_processors/gefs_downloader.py`:

- In `__init__`:
  - Compute `self.lead_start = min(self.forecast_hours)` and `self.lead_end = max(self.forecast_hours)`.
  - Build `gefs_dir = build_gefs_processed_dir(self.location, self.lead_start, self.lead_end)`.
  - Basename `build_gefs_basename(kind="freq-3h", ...)`.
  - Set `self.output_file = os.path.join(gefs_dir, f"{basename}.csv")`.
- Ensure `os.makedirs(gefs_dir, exist_ok=True)` before writing.
- After the main loop (end of `download()`):
  - `finalize_csv_with_date_range(self.output_file, date_col="valid_time")`.

This preserves resume/backup logic; only changes where the file is written and how it’s finalized.

#### 3) GEFS aggregator: write “sum” CSV into the same directory with standardized name

- Default output path should be in the same directory as the input per-hour file, using:
  - Basename `build_gefs_basename(kind="sum", ...)` and date range `YYYYMMDD-YYYYMMDD` derived from `valid_datetime_start`/`valid_datetime_end`.
- In `GefsAggregator.aggregate()`:
  - Compute `date_range_str` from min/max of `valid_datetime_start` (start) and `valid_datetime_end` (end - 1 second).
  - Build final path:
    - `out_dir = os.path.dirname(self.output_csv)` (or derive from the input per-hour file).
    - `final_name = f"{sum_basename}_{date_range_str}.csv"`.
    - Write to `os.path.join(out_dir, final_name)`.

Note: If you keep `scripts/aggregate_gefs.py` accepting explicit `--output-csv`, ensure the default points to the per-hour directory and replaces `freq-3h` with `sum`.

#### 4) ERA5 NetCDF extraction (hourly CSV)

Edit `scripts/extract_era5_to_csv.py`:

- Before calling `extract_to_csv`, compute:
  - `output_dir = build_era5_processed_dir((lat, lon), variable=var, frequency="hourly")`
- In `NetCDFDataExtractor.extract_to_csv()` (or call-site), standardize the output filename to use `build_era5_basename(var, "hourly", (lat, lon))` rather than inheriting the NetCDF base name:
  - `base = build_era5_basename(var, "hourly", (lat, lon))`
  - `final_name = f"{base}_{date_range}.csv"`

Keep date range inferred from data/file (`valid_time` min/max).

#### 4b) ERA5 downloader and raw naming (standardize raw NetCDF paths)

Update `scripts/download_era5.py` and `src/hydro/data_processors/era5_downloader.py` so raw NetCDF files follow a structured directory and filename convention aligned with processed outputs.

- Raw directory (by grid and variable):

  - `data/raw/era5/lat-<lat>_lon-<lon>/<variable>/`
  - Examples:
    - `data/raw/era5/lat-47p5_lon-8p0/tp/`
    - `data/raw/era5/lat-47p5_lon-8p0/t2m/`

- Raw NetCDF filename pattern:

  - `era5_<var>_lat-<lat>_lon-<lon>_YYYYMMDD-YYYYMMDD.nc`
  - Examples:
    - `era5_tp_lat-47p5_lon-8p0_20250101-20250131.nc`
    - `era5_t2m_lat-47p5_lon-8p0_20250101-20250131.nc`

- Code changes:
  - `src/hydro/data_processors/era5_downloader.py`:
    - Import and use `grid_tags(lat, lon)` from `hydro.common`.
    - Update `build_output_path(variable, start_date, end_date)` to:
      - Build `out_dir = os.path.join(RAW_ERA5_DIR, grid_tags(*location), variable)`
      - Ensure directory exists.
      - Build filename with date range using hyphen: `YYYYMMDD-YYYYMMDD`.
      - Return `.nc` final path (the downloader should replace ZIP with `.nc` after extraction if needed).
  - `scripts/download_era5.py`:
    - Add optional `--lat` and `--lon` flags (defaults to `GRID_RHINE_POINT`).
    - Pass `(args.lat, args.lon)` to `Era5Downloader`.
    - Log the final raw output path.
  - `scripts/extract_era5_to_csv.py` (compat):
    - If you choose to nest raw files in subdirectories, update `find_era5_files()` to support recursive search when `--raw-dir` is the root, e.g., `glob(os.path.join(raw_dir, "**", f"era5_{var}_*.nc"), recursive=True)`.

Notes:

- This step keeps raw and processed naming parallel, easing multi-location workflows and preventing filename collisions.
- If you prefer to avoid recursive search, pass the var-specific grid directory via `--raw-dir`.

#### 5) ERA5 daily aggregator

Edit `src/hydro/data_processors/era5_aggregator.py`:

- Write outputs to:
  - `processed_dir = build_era5_processed_dir((lat, lon), variable, "daily")`
  - Use standardized basename:
    - `base = build_era5_basename(variable, "daily", (lat, lon))`
    - `out_filename = f"{base}_{date_range}.csv"`
  - Ensure `os.makedirs(processed_dir, exist_ok=True)`.

You can infer lat/lon from the input hourly filename using the `lat-..._lon-...` part, or pass location explicitly if available.

#### 6) Dataset assembler discovery

Edit `src/hydro/data_processors/dataset_assembler.py` to discover new paths first, then fall back to old:

- GEFS aggregated (new):
  - `glob(os.path.join(PROCESSED_DIR, "gefs", "**", "gefs_tp_sum_*.csv"), recursive=True)`
- Fallback (old):
  - `glob(os.path.join(PROCESSED_DIR, "gefs_ensemble_tp*.csv"))`
- ERA5 daily (new):
  - `glob(os.path.join(PROCESSED_DIR, "era5", "**", "era5_tp_daily_*.csv"), recursive=True)`
  - `glob(os.path.join(PROCESSED_DIR, "era5", "**", "era5_t2m_daily_*.csv"), recursive=True)`
- Fallback (old):
  - `glob(os.path.join(PROCESSED_DIR, "era5_tp_daily_*.csv"))`
  - `glob(os.path.join(PROCESSED_DIR, "era5_t2m_daily_*.csv"))`

Keep the existing sorting (mtime) and validation.

---

### Context notes

- Valid-time semantics:
  - GEFS per-hour: finalize with min/max of `valid_time`.
  - GEFS sum: finalize with min(`valid_datetime_start`) to max(`valid_datetime_end`) − 1 sec, formatted as `YYYYMMDD-YYYYMMDD`.
  - ERA5 hourly/daily: min/max of `valid_time` (hourly) or daily boundaries (daily).
- Cycle remains in GEFS filenames as `cycle-00z` to avoid collisions if adding 06/12/18z later.
- If step length differs in future (e.g., 6-hourly), change `freq-3h` accordingly.

---

### Plan checklist

- Implement helpers in `src/hydro/common.py`:
  - `PROCESSED_GEFS_DIR`, `PROCESSED_ERA5_DIR`
  - `grid_tags(...)`
  - `build_gefs_processed_dir(...)`, `build_gefs_basename(...)`
  - `finalize_csv_with_date_range(...)`
  - `build_era5_processed_dir(...)`, `build_era5_basename(...)`
- GEFS downloader (`src/hydro/data_processors/gefs_downloader.py`):
  - Use new processed directory and `freq-3h` basename.
  - Finalize per-hour CSV with valid-time range.
- GEFS aggregator:
  - Output to same directory, use `sum` basename + date range.
  - Ensure default output path in `scripts/aggregate_gefs.py` matches the new convention or infer from input.
- ERA5 hourly extraction (`scripts/extract_era5_to_csv.py` + `NetCDFDataExtractor`):
  - Use new `era5/<grid>/<var>/hourly` directory.
  - Output filenames via `build_era5_basename(..., "hourly", ...)`.
- ERA5 downloader and raw naming (`scripts/download_era5.py` + `src/hydro/data_processors/era5_downloader.py`):
  - Write raw NetCDFs to `raw/era5/<grid>/<var>/` with standardized filenames.
  - Add `--lat/--lon` flags to the download script and log final paths.
  - Optionally make extractor's raw search recursive to support nested dirs.
- ERA5 daily aggregator (`src/hydro/data_processors/era5_aggregator.py`):
  - Use new `era5/<grid>/<var>/daily` directory.
  - Output filenames via `build_era5_basename(..., "daily", ...)`.
- Dataset assembler (`src/hydro/data_processors/dataset_assembler.py`):
  - Update discovery to search new structure first, fallback to old.
- Update docs (`docs/data_processing_guide.md`, `docs/project_structure.md`) to reflect structure and filenames.
- Sanity checks:
  - Run a short GEFS download (`--test`) and verify per-hour file path/name.
  - Aggregate the per-hour CSV; verify `sum` file path/name.
  - Run ERA5 download/extract; verify hourly and daily output paths/names.
  - Ensure assembler auto-discovers new files.
- Optional:
  - Add `ver-v1` to filenames if schema changes are expected soon.
  - Add simple unit tests for helper functions in `hydro/common.py`.

---

### Examples (final)

```text
data/processed/gefs/lat-47p5_lon-8p0/lead_120-168/gefs_tp_freq-3h_lat-47p5_lon-8p0_lead-120-168_cycle-00z_20230101-20250215.csv
data/processed/gefs/lat-47p5_lon-8p0/lead_120-168/gefs_tp_sum_lat-47p5_lon-8p0_lead-120-168_cycle-00z_20230101-20250215.csv
data/processed/era5/lat-47p5_lon-8p0/tp/hourly/era5_tp_freq-1h_lat-47p5_lon-8p0_20230101-20250215.csv
data/processed/era5/lat-47p5_lon-8p0/tp/daily/era5_tp_daily_lat-47p5_lon-8p0_20230101-20250215.csv
data/processed/era5/lat-47p5_lon-8p0/t2m/hourly/era5_t2m_freq-1h_lat-47p5_lon-8p0_20230101-20250215.csv
data/processed/era5/lat-47p5_lon-8p0/t2m/daily/era5_t2m_daily_lat-47p5_lon-8p0_20230101-20250215.csv
```
