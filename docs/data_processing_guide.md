# Data Processing Guide (GEFS + ERA5)

This guide explains the constants defined in `src/hydro/common.py` and the exact steps (and commands) to download and process GEFS and ERA5 data before combining for exploration/modeling.

## Constants (from `hydro.common`)

- `RHINE_POINT = (47.5565597, 8.0483)`
  - The original lat/lon point of interest.
- `GRID_RHINE_POINT = (47.5, 8.0)`
  - Nearest grid-aligned point used for both GEFS and ERA5.
- `PROJECT_ROOT`
  - Absolute path to the repository root.
- `SCRIPTS_DIR`
  - `PROJECT_ROOT/scripts` (where logs and script-specific outputs/checkpoints live).
- `DATA_DIR`
  - `PROJECT_ROOT/data` (root for datasets).
- `RAW_ERA5_DIR`
  - `PROJECT_ROOT/data/raw/era5` (download destination for ERA5 NetCDF files).
- `INTERIM_GEFS_DIR`
  - `PROJECT_ROOT/data/interim/gefs` (temporary working storage for GEFS GRIB files).
- `PROCESSED_DIR`
  - `PROJECT_ROOT/data/processed` (final CSV outputs for both GEFS and ERA5).
- `grid_point_string(lat, lon)`
  - Formats coordinates as a filename-safe string like `(47p5,8p0)`.

## Prerequisites

- Use this Python interpreter:

  ```bash
  /Users/williamhenry/python_venvs/hydro_poc/bin/python --version
  ```

- Dependencies are managed via pip-tools. If needed:

  ```bash
  /Users/williamhenry/python_venvs/hydro_poc/bin/python -m pip install pip-tools
  /Users/williamhenry/python_venvs/hydro_poc/bin/python -m piptools sync requirements.txt
  ```

- For ERA5 downloads: configure `cdsapi` credentials in `~/.cdsapirc`.

## GEFS: Download and Aggregate

Note: GEFS source data (NOAA) is hosted in AWS `us-east-1`. For faster download and lower latency, it is recommended to run the GEFS download step on an EC2 instance in `us-east-1`.

1. Download GEFS ensemble precipitation (00z cycles, lead hours 120–168 processed later)

- Script: `scripts/download_gefs.py`
- Outputs:
  - GRIB files → `data/interim/gefs/` (temporary, deleted after processing)
  - Per-hour extraction CSV → `data/processed/gefs_ensemble_tp.csv`
  - Logs/checkpoint → `scripts/gefs_download.log`, `scripts/gefs_checkpoint.json`

Examples:

```bash
# From repo root
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/download_gefs.py \
  --start-date 2025-01-01 \
  --end-date 2025-01-31

# Resume from checkpoint if interrupted
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/download_gefs.py \
  --start-date 2025-01-01 --end-date 2025-01-31 --resume
```

2. Aggregate GEFS total precipitation for the target window (e.g., 120–168 hours)

- Script: `scripts/aggregate_gefs.py`
- Input: `data/processed/gefs_ensemble_tp.csv`
- Output: `data/processed/gefs_ensemble_tp_(47p5,8p0)_120-168.csv` (or similar)

Examples:

```bash
# Default 120–168 hours (step=3). Writes a suffixed CSV next to the input.
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/aggregate_gefs.py

# Customize input/output and lead-hours
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/aggregate_gefs.py \
  --input-csv data/processed/gefs_ensemble_tp.csv \
  --start-hour 120 --end-hour 168 --step 3 \
  --output-csv data/processed/gefs_ensemble_tp_120-168.csv
```

## ERA5: Download, Extract to CSV, Aggregate Daily

1. Download ERA5 reanalysis (NetCDF) for `tp` and `t2m`

- Script: `scripts/download_era5.py`
- Input: date range and variable (`tp` or `t2m`)
- Output: NetCDF in `data/raw/era5/era5_<var>_<YYYYMMDD>_<YYYYMMDD>.nc`
- Notes:
  - The downloader transparently handles cases where CDS returns a ZIP and extracts the inner `.nc` file.

Examples:

```bash
# Total precipitation
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/download_era5.py \
  --variable tp --start-date 2025-01-01 --end-date 2025-01-31

# 2m temperature
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/download_era5.py \
  --variable t2m --start-date 2025-01-01 --end-date 2025-01-31
```

2. Extract ERA5 NetCDFs to hourly CSV time series at the grid point

- Script: `scripts/extract_era5_to_csv.py`
- Scans `data/raw/era5/era5_*.nc` and writes per-file CSVs to `data/processed/`
- Output filenames include variable and grid point: e.g., `era5_tp_(47p5,8p0)_20250101_20250131.csv`

Example:

```bash
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/extract_era5_to_csv.py \
  --variables tp t2m
```

3. Aggregate ERA5 hourly to daily to align with GEFS daily valid windows

- Script: `scripts/aggregate_era5_daily.py`
- Inputs: ERA5 hourly CSVs in `data/processed/` (produced by step 2)
- Outputs (in `data/processed/`):
  - `era5_tp_daily_(47p5,8p0)_<start>_<end>.csv`: daily sum of `tp`
  - `era5_t2m_daily_(47p5,8p0)_<start>_<end>.csv`: daily `min`,`mean`,`max` of `t2m`
- Units:
  - ERA5 `tp` is in meters (m). The daily aggregator multiplies by 1000 to convert to millimeters (mm), aligning with GEFS where `kg m^-2` ≡ `mm`.

Example:

```bash
# Aggregate all ERA5 hourly CSVs found in data/processed
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/aggregate_era5_daily.py data/processed
```

## Outputs Summary

- GEFS per-hour extraction: `data/processed/gefs_ensemble_tp.csv`
- GEFS aggregated window: `data/processed/gefs_ensemble_tp_*_120-168.csv`
- ERA5 hourly CSVs: `data/processed/era5_tp_(47p5,8p0)_<start>_<end>.csv`, `era5_t2m_(...)`
- ERA5 daily aggregated: `data/processed/era5_tp_daily_(47p5,8p0)_<start>_<end>.csv`, `era5_t2m_daily_(...)`

At this point, the daily GEFS and ERA5 datasets are ready to be merged into a modeling dataset. See the next sections to assemble the dataset and split into train/test.

## Assemble Merged Dataset (GEFS + ERA5)

Build a single, wide CSV that contains:

- Pivoted GEFS member columns (e.g., `gefs_gec00`, `gefs_gep01`, ...)
- ERA5 daily truth aligned to the GEFS valid window (`era5_tp`)
- Lag-1 predictors from ERA5 (`era5_tp_lag1`, `era5_t2m_min/mean/max_lag1`)
- GEFS ensemble statistics derived from perturbed members (`gefs_ensemble_min`, `gefs_ensemble_max`, `gefs_ensemble_q10`, `gefs_ensemble_q90`, `gefs_ensemble_skew`, `gefs_ensemble_kurtosis`)
- Monthly indicator columns based on `valid_datetime_start` (`jan`..`dec`)

- Script: `scripts/build_dataset.py`
- Inputs:
  - GEFS aggregated CSV(s): `data/processed/gefs_ensemble_tp_(<grid>)_<lead-range>_<dates>.csv`
  - ERA5 daily tp: `data/processed/era5_tp_daily_(<grid>)_<dates>.csv`
  - ERA5 daily t2m: `data/processed/era5_t2m_daily_(<grid>)_<dates>.csv`
- Output:
  - `data/processed/dataset_gefs_era5_(<grid>)_<lead-range>_<start>_<end>.csv`

Examples:

```bash
# Auto-detect latest ERA5 daily files and all matching GEFS aggregated CSVs
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/build_dataset.py

# Explicit inputs and output
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/build_dataset.py \
  --gefs-csv data/processed/gefs_ensemble_tp_(47p5,8p0)_120-144_20230106_20250206.csv \
  --era5-tp-daily data/processed/era5_tp_daily_(47p5,8p0)_20230101_20250215.csv \
  --era5-t2m-daily data/processed/era5_t2m_daily_(47p5,8p0)_20230101_20250215.csv \
  --output-csv data/processed/dataset_gefs_era5_(47p5,8p0)_120-144_20230106_20250206.csv
```

Notes:

- If `--gefs-csv/--era5-*` are omitted, the script auto-discovers files in `data/processed/`.
- The output filename includes the grid, lead-hour range, and min/max valid dates found in the data.

## Split Dataset into Training and Testing

Split the assembled dataset into train and test CSVs by `valid_datetime_start` date range. Date ranges must not overlap.

- Script: `scripts/split_dataset.py`
- Input: `data/processed/dataset_gefs_era5_(<grid>)_<lead-range>_<start>_<end>.csv`
- Outputs (written next to the input file):
  - `..._<trainStart>_<trainEnd>_train.csv`
  - `..._<testStart>_<testEnd>_test.csv`

Example:

```bash
/Users/williamhenry/python_venvs/hydro_poc/bin/python scripts/split_dataset.py \
  data/processed/dataset_gefs_era5_(47p5,8p0)_120-144_20230101_20250205.csv \
  --train-start 2023-01-01 --train-end 2023-12-31 \
  --test-start 2024-01-01 --test-end 2025-02-05
```

Final Outputs Summary:

- Merged modeling dataset: `data/processed/dataset_gefs_era5_(<grid>)_<lead-range>_<start>_<end>.csv`
- Train/Test splits: `..._<trainStart>_<trainEnd>_train.csv`, `..._<testStart>_<testEnd>_test.csv`
