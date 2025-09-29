# GEFS Precipitation Post-Processing POC

A proof-of-concept machine learning project for improving GEFS (Global Ensemble Forecast System) precipitation ensemble forecasts through post-processing, with a focus on extreme precipitation events for hydropower applications.

The focus will be in the Laufenburg region, specifically around the Laufenburg hydropower plant on the Swiss-German border. This is part of the High Rhine sub-basin, which is a hydropower-heavy region.

## Overview

This project demonstrates how to adjust GEFS ensemble precipitation forecasts to better capture tail events (extreme rainfall) using two approaches:

- **CRPS-optimized Gamma Neural Network**: A deterministic neural network trained with Continuous Ranked Probability Score (CRPS) loss
- **Bayesian Neural Network**: A probabilistic approach providing uncertainty quantification

The project targets a specific Rhine basin location (47.5565597°N, 8.0483°E) and compares raw GEFS performance against post-processed forecasts, emphasizing improvements in extreme precipitation prediction.

## Features

- **Automated GEFS Data Acquisition**: Downloads and processes GEFS ensemble data from NOAA's AWS Open Data
- **ERA5 Ground Truth Integration**: Incorporates ERA5 reanalysis data for reliable ground truth observations
- **Incremental Processing**: Memory-efficient CSV saving with checkpointing for large-scale processing
- **Modular Architecture**: Clean separation between data acquisition, processing, and modeling
- **Reproducible Environment**: Full dependency management with `pip-tools`

## Installation

### Prerequisites

- Python 3.10+
- A virtual environment (recommended)

### Quick Start

1. **Clone the repository** (if applicable) or navigate to the project directory:

   ```bash
   cd /path/to/hydro_poc
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python -m venv hydro_poc_env
   source hydro_poc_env/bin/activate  # On Windows: hydro_poc_env\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install pip-tools
   pip-compile  # Updates requirements.txt including the editable package
   pip-sync     # Syncs environment with exact versions and installs the package
   ```

### Dependencies

Key dependencies include:

- `xarray`, `pandas`: Data manipulation
- `cfgrib`: GRIB2 file handling for meteorological data
- `boto3`: AWS S3 access for GEFS data
- `cdsapi`: Copernicus Climate Data Store for ERA5 data
- `matplotlib`, `plotly`: Visualization
- `jupyter`: Interactive development

## Usage

### Data Acquisition

#### GEFS Ensemble Data

Download GEFS ensemble precipitation data for a specified date range:

```bash
# Download for a single date (local testing)
python scripts/download_gefs_ensemble.py --start-date 2025-01-01 --end-date 2025-01-01

# Download for multiple dates (AWS deployment)
python scripts/download_gefs_ensemble.py --start-date 2025-01-01 --end-date 2025-01-31 --output-dir /path/to/output
```

#### ERA5 Reanalysis Data

Download ERA5 precipitation and temperature data for ground truth and predictors:

```bash
# Download precipitation data
python scripts/download_era5.py --variable tp --start-date 2025-01-01 --end-date 2025-01-31

# Download temperature data
python scripts/download_era5.py --variable t2m --start-date 2025-01-01 --end-date 2025-01-31
```

### Development Workflow

1. **Data Processing**: Use Jupyter notebooks in the `notebooks/` directory for exploratory analysis
2. **Model Development**: Implement and compare CRPS-optimized and Bayesian neural networks
3. **Evaluation**: Compare baseline GEFS performance against post-processed forecasts

### Project Structure

See `docs/project_structure.md` for the project structure.
