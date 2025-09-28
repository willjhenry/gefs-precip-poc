# ERA5 Data Acquisition and Processing Task

## Overview

Download and process ERA5 reanalysis data to serve as ground truth observations and predictors for the GEFS precipitation post-processing project. This task provides the "observed" precipitation and lagged variables needed for model training and evaluation.

## Problem Statement

- Need accurate ground truth precipitation observations for Rhine basin point to validate GEFS ensemble forecasts
- Require lagged predictors (previous days' precipitation and temperature) for time series modeling
- Must match GEFS data temporally (2025-01-01 to 2025-01-31) and spatially (Rhine basin point: 47.5565597°N, 8.0483°E)
- ERA5 data needs daily resampling and quality checks for ML-ready format

## Solution Approach

Use Copernicus Climate Data Store (CDS) API to download ERA5 reanalysis data, then process into daily aggregates with lagged features for integration with GEFS ensemble data.

## Key Requirements

- **Time Period**: 2025-01-01 to 2025-01-31 (matching GEFS POC run)
- **Spatial Coverage**: Single point extraction at Rhine basin location (47.5565597, 8.0483)
- **Variables**:
  - Total precipitation (tp) - ground truth observations
  - 2m temperature (t2m) - predictor variable
- **Temporal Resolution**: Hourly downloads, resample to daily totals/averages
- **Output Format**: CSV with daily data and lagged features

## Detailed Tasks

- [ ] **Set up CDS API credentials** - Install cdsapi, obtain API key from CDS website
- [ ] **Create ERA5 download script** - Python script using cdsapi to fetch hourly data
- [ ] **Download precipitation data** - Total precipitation (tp) for target period/location
- [ ] **Download temperature data** - 2m temperature (t2m) for predictors
- [ ] **Resample to daily** - Aggregate hourly data to daily totals (precip) and averages (temp)
- [ ] **Create lagged features** - Add lag-1 and lag-2 precipitation/temperature columns
- [ ] **Data validation** - Check for missing values, quality flags, reasonable ranges
- [ ] **Format for ML** - Match GEFS date format, prepare for 80/20 train/test split
- [ ] **Save processed data** - CSV file with columns: date, tp_daily, t2m_daily, tp_lag1, tp_lag2, t2m_lag1, t2m_lag2

## Success Criteria

- [ ] **ERA5 data downloaded** - Hourly tp and t2m for January 2025 at Rhine point
- [ ] **Daily aggregation complete** - Proper resampling with no data gaps
- [ ] **Lagged features created** - lag-1 and lag-2 for both precip and temp
- [ ] **Data quality validated** - No missing values, reasonable physical ranges
- [ ] **Integration ready** - CSV format matches GEFS data for merging
- [ ] **Processing time reasonable** - Downloads complete in <2 hours, processing <10 minutes

## Deliverables

- [ ] **ERA5 download script** - Reusable Python script with cdsapi integration
- [ ] **Raw ERA5 data files** - Hourly NetCDF files (optional: can delete after processing)
- [ ] **Processed ERA5 CSV** - `era5_rhine_daily.csv` with all features
- [ ] **Data quality report** - Summary of download success, missing data, ranges
- [ ] **Integration code** - Script to merge ERA5 with GEFS data for ML pipeline

## Technical Implementation Notes

**CDS API Setup:**

```python
# Install: pip install cdsapi
# API key in ~/.cdsapirc or environment variables
import cdsapi

c = cdsapi.Client()
c.retrieve(
    'reanalysis-era5-single-levels',
    {
        'product_type': 'reanalysis',
        'variable': ['total_precipitation', '2m_temperature'],
        'year': '2025',
        'month': '01',
        'day': list(range(1, 32)),
        'time': [f'{h:02d}:00' for h in range(24)],
        'area': [48, 8, 47, 9],  # [N, W, S, E] - small box around Rhine point
        'format': 'netcdf',
    },
    'era5_rhine_hourly.nc'
)
```

**Data Processing Steps:**

1. Load NetCDF with xarray
2. Extract point data: `ds.sel(latitude=47.5565597, longitude=8.0483, method='nearest')`
3. Resample hourly to daily:
   - Precip: sum (mm/day)
   - Temp: mean (°C)
4. Create lags: shift(-1), shift(-2)
5. Handle missing data: interpolate or drop
6. Save to CSV

**File Size Estimates:**

- Hourly data: ~50MB per month for single point
- Daily processed: ~1KB CSV

**Error Handling:**

- API rate limits: Implement retries with exponential backoff
- Missing data: Check ERA5 quality flags
- Coordinate precision: Ensure point extraction accuracy

**Integration with GEFS:**

- Use same date format (YYYYMMDD)
- Align temporal coverage exactly
- Prepare for pandas merge on date column
