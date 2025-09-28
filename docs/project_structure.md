/Users/williamhenry/Documents/1_Projects/hydro_poc/
├── notebooks/ # Jupyter notebooks for each development phase
│ ├── 01_data_acquisition.ipynb
│ ├── 02_eda.ipynb
│ ├── 03_baseline_evaluation.ipynb
│ ├── 04_crps_nn.ipynb
│ ├── 05_bayesian_nn.ipynb
│ └── 06_evaluation.ipynb
├── scripts/ # Command-line executable scripts (logs/checkpoints stored here)
│ ├── download_gefs_ensemble.py # GEFS ensemble tp extraction (GRIB → CSV)
│ ├── download_era5.py # ERA5 reanalysis download (NetCDF)
│ ├── gefs_download.log
│ ├── era5_download.log
│ └── gefs_checkpoint.json
├── src/ # Reusable Python package (editable install)
│ └── hydro/
│ ├── **init**.py
│ ├── common.py # Shared constants (e.g., GRID_RHINE_POINT)
│ └── data_processors/
│ ├── **init**.py
│ ├── era5_downloader.py # Era5Downloader class used by scripts/download_era5.py
│ └── gefs_aggregator.py # GefsAggregator class used by scripts/aggregate_gefs_tp_120_168.py
├── data/ # Data storage (gitignored)
│ ├── raw/
│ │ └── era5/ # ERA5 NetCDF downloads
│ ├── processed/
│ │ ├── gefs_ensemble_tp.csv # Raw per-hour tp from GEFS ensembles
│ │ └── gefs_ensemble_tp_120_168.csv # Aggregated tp (120-168 hours) from GefsAggregator
│ └── interim/
│ └── gefs/ # Temporary GRIB downloads during processing
├── models/ # Saved model artifacts (gitignored)
├── results/ # Outputs and visualizations
│ ├── plots/
│ ├── metrics/
│ └── reports/
├── tests/ # Unit tests (optional)
├── docs/ # Documentation (already exists)
├── .gitignore # Ignore data/, models/, **pycache**/
├── requirements.txt # Already exists
└── README.md # Project overview and setup
