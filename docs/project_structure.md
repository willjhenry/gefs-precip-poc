/Users/williamhenry/Documents/1_Projects/hydro_poc/
├── notebooks/ # Jupyter notebooks for each development phase
│ ├── 01_data_acquisition.ipynb
│ ├── 02_eda.ipynb
│ ├── 03_baseline_evaluation.ipynb
│ ├── 04_crps_nn.ipynb
│ ├── 05_bayesian_nn.ipynb
│ └── 06_evaluation.ipynb
├── scripts/ # Command-line executable scripts
│ ├── download_gefs.py # CLI wrapper for GEFS download
│ ├── download_era5.py # CLI wrapper for ERA5 download
│ └── preprocess_data.py # CLI wrapper for preprocessing pipeline
├── src/ # Reusable Python modules
│ ├── data/
│ │ ├── **init**.py
│ │ ├── download_gefs.py # Core GEFS download functions
│ │ ├── download_era5.py # Core ERA5 download functions
│ │ └── preprocessing.py # Core preprocessing functions
│ ├── models/
│ │ ├── **init**.py
│ │ ├── crps_nn.py
│ │ ├── bayesian_nn.py
│ │ └── evaluation.py
│ └── utils/
│ ├── **init**.py
│ ├── plotting.py
│ ├── metrics.py
│ └── config.py
├── data/ # Data storage (gitignored)
│ ├── raw/ # Original GEFS/ERA5 downloads
│ ├── processed/ # Cleaned datasets
│ └── interim/ # Temporary processing files
├── models/ # Saved model artifacts (gitignored)
├── results/ # Outputs and visualizations
│ ├── plots/
│ ├── metrics/
│ └── reports/
├── tests/ # Unit tests (optional)
├── docs/ # Documentation (already exists)
├── .gitignore # Ignore data/, models/, **pycache**/
├── pyproject.toml # Python project configuration
├── requirements.txt # Already exists
└── README.md # Project overview and setup
