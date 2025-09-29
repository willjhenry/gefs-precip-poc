# GEFS Precipitation Post-Processing POC Weekend Project

A proof-of-concept machine learning project for improving GEFS (Global Ensemble Forecast System) precipitation ensemble forecasts through post-processing, with a focus on extreme precipitation events for hydropower applications.

The focus will be in the Laufenburg region, specifically around the Laufenburg hydropower plant on the Swiss-German border. This is part of the High Rhine sub-basin, which is a hydropower-heavy region. Attempts will be made to improve upon the GEFS ensemble total precipitation 120-144h forecast for the Laufenburg region (one grid point for now).

See the luafenburg_precip_forecast_exploration.ipynb notebook for the exploration of the data and the model(s). Code for downloading and arranging the data is in the scripts/ directory. A 'hydro' python package is used for the models and data processing classes.

## Overview

This project demonstrates how to adjust GEFS ensemble precipitation forecasts to better capture tail events (extreme rainfall) using two approaches:

- **CRPS-optimized Gamma Neural Network**: A deterministic neural network trained with Continuous Ranked Probability Score (CRPS) loss

- **Bayesian Neural Network**: (Not implemented yet) A probabilistic approach providing uncertainty quantification

The project targets a specific Rhine basin location (47.5565597°N, 8.0483°E) and compares raw GEFS performance against post-processed forecasts, emphasizing improvements in extreme precipitation prediction.

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

## Usage

### Project Structure

See `docs/project_structure.md` for the project structure.

### Data Acquisition

See the docs/data_processing_guide.md file for the data processing guide.

## TODOs

- Implement the Bayesian Neural Network
- Clean up and streamline data getting and processing code
