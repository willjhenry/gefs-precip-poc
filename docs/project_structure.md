project_root/
├── notebooks/ # Jupyter notebooks for exploration/modeling
│ ├── laufenburg_precip_forecast_exploration.ipynb
│ ├── noaa_gfs_quickstart.ipynb
│ └── noaa_gfs_quickstart_my_edits.ipynb
├── scripts/ # Command-line executable scripts (logs/checkpoints stored here)
│ ├── download_gefs.py # GEFS ensemble tp extraction (GRIB → CSV)
│ ├── aggregate_gefs.py # Aggregate GEFS tp over lead-hour window
│ ├── download_era5.py # ERA5 reanalysis download (NetCDF)
│ ├── extract_era5_to_csv.py # Extract NetCDF → hourly CSV at grid point
│ ├── aggregate_era5_daily.py # Aggregate ERA5 hourly → daily tp/t2m stats
│ ├── build_dataset.py # Assemble merged dataset (GEFS+ERA5, lags, stats, month dummies)
│ ├── split_dataset.py # Split merged dataset into train/test by date
│ └── gefs_checkpoint.json
├── src/ # Reusable Python package (editable install)
│ └── hydro/
│ ├── **init**.py
│ ├── common.py # Shared constants/paths (e.g., PROCESSED_DIR, grid_point_string)
│ └── data_processors/
│ │ ├── **init**.py
│ │ ├── gefs_downloader.py # Used by scripts/download_gefs.py
│ │ ├── gefs_aggregator.py # Aggregation of GEFS tp totals
│ │ ├── era5_downloader.py # Used by scripts/download_era5.py
│ │ ├── netcdf_extractor.py # NetCDF → CSV extraction
│ │ ├── era5_aggregator.py # ERA5 hourly → daily aggregations
│ │ └── dataset_assembler.py # Assemble merged modeling dataset
│ ├── models/
│ │ └── **init**.py
│ └── utils/
│ ├── **init**.py
│ └── skill.py # Metrics/helpers
├── data/ # Data storage (gitignored)
│ ├── raw/
│ │ └── era5/ # ERA5 NetCDF downloads
│ ├── interim/
│ │ └── gefs/ # Temporary GEFS GRIB downloads
│ └── processed/ # Final CSV outputs
├── results/ # Outputs and visualizations
│ ├── plots/
│ ├── metrics/
│ └── reports/
├── model_artifacts/ # Placeholder for saved models
├── tests/ # Unit tests (optional)
├── docs/ # Documentation
│ ├── data_processing_guide.md
│ ├── project_outline.md
│ ├── project_structure.md
│ ├── notes.md
│ └── task_docs/
│ ├── aws_gefs_poc.md
│ ├── era5_data_acquisition.md
│ └── project_progress.md
├── requirements.in
├── requirements.txt
├── requirements-dev.in
├── requirements-dev.txt
├── pyproject.toml
├── setup.py
├── README.md
└── .gitignore # Ignore data/, models/, **pycache**/
