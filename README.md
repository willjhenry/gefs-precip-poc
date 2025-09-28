# GEFS Precipitation Post-Processing POC

A proof-of-concept machine learning project for improving GEFS (Global Ensemble Forecast System) precipitation ensemble forecasts through post-processing, with a focus on extreme precipitation events for hydropower applications.

## Overview

This project demonstrates how to adjust GEFS ensemble precipitation forecasts to better capture tail events (extreme rainfall) using two approaches:

- **CRPS-optimized Neural Network**: A deterministic neural network trained with Continuous Ranked Probability Score (CRPS) loss
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

```
hydro_poc/
├── notebooks/          # Jupyter notebooks for analysis and development
├── scripts/            # Command-line scripts for data acquisition
│   ├── download_gefs_ensemble.py
│   └── download_era5.py
├── src/hydro/          # Main package
│   ├── common.py       # Shared constants and utilities
│   ├── data/           # Data processing modules
│   ├── models/         # ML model implementations
│   └── utils/          # Utility functions
├── data/               # Data storage (gitignored)
│   ├── raw/            # Original downloads
│   ├── processed/      # Clean datasets
│   └── interim/        # Temporary files
├── models/             # Saved model artifacts (gitignored)
├── results/            # Outputs and visualizations
│   ├── plots/
│   ├── metrics/
│   └── reports/
├── docs/               # Documentation
│   ├── project_outline.md
│   ├── project_structure.md
│   └── task_docs/      # Detailed task documentation
└── tests/              # Unit tests
```

## Development Status

**Current Phase**: Phase 1 (Data Acquisition) - 80% Complete

- ✅ GEFS download pipeline with robust error handling
- ✅ Incremental CSV processing with checkpointing
- ✅ Local testing validated
- ✅ AWS deployment script ready
- 🔄 ERA5 data acquisition (in progress)
- ⏳ Phases 2-6 (EDA, baseline evaluation, neural networks, comparison)

See `docs/task_docs/project_progress.md` for detailed progress tracking.

## Key Technical Concepts

- **GEFS**: NOAA's Global Ensemble Forecast System (30 perturbed members + control + spread + mean)
- **GRIB2**: Meteorological data format requiring selective variable extraction
- **CRPS**: Continuous Ranked Probability Score for probabilistic forecast evaluation
- **Ensemble Post-processing**: Statistical correction of raw ensemble forecasts
- **Tail Calibration**: Improving predictions of extreme events (heavy precipitation)

## Contributing

1. Follow the established project structure
2. Use the specified Python executable: `/Users/williamhenry/python_venvs/hydro_poc/bin/python`
3. Update `requirements.in` for new dependencies, then run `pip-compile && pip-sync`
4. Add tests in the `tests/` directory
5. Update documentation in `docs/`

## License

This project is for educational and research purposes. Please check NOAA and Copernicus data usage policies for commercial applications.

## Contact

For questions about the GEFS post-processing methodology or implementation details, refer to the documentation in `docs/` or check the Jupyter notebooks for code examples.
