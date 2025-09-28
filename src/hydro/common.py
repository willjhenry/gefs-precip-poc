"""Shared constants for the Hydro POC project."""

import os

RHINE_POINT = (47.5565597, 8.0483)
GRID_RHINE_POINT = (47.5, 8.0)

# Project paths (computed relative to this file's location)
PROJECT_ROOT: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
SCRIPTS_DIR: str = os.path.join(PROJECT_ROOT, "scripts")
DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
RAW_ERA5_DIR: str = os.path.join(DATA_DIR, "raw", "era5")

INTERIM_GEFS_DIR = os.path.join(DATA_DIR, "interim", "gefs")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
