#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import re
import sys

import pandas as pd

from hydro.common import PROCESSED_DIR, SCRIPTS_DIR

"""Set up logging configuration."""
LOG_FILE = os.path.join(SCRIPTS_DIR, "split_dataset.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split a dataset CSV into train and test sets by valid_datetime_start date ranges."
    )
    parser.add_argument(
        "dataset_csv",
        help="Path to the merged dataset CSV.",
    )
    parser.add_argument(
        "--train-start",
        required=True,
        help="Start date for training set (inclusive, YYYY-MM-DD).",
    )
    parser.add_argument(
        "--train-end",
        required=True,
        help="End date for training set (inclusive, YYYY-MM-DD).",
    )
    parser.add_argument(
        "--test-start",
        required=True,
        help="Start date for test set (inclusive, YYYY-MM-DD).",
    )
    parser.add_argument(
        "--test-end",
        required=True,
        help="End date for test set (inclusive, YYYY-MM-DD).",
    )
    parser.add_argument(
        "--output-dir",
        default=PROCESSED_DIR,
        help="Directory to write train and test CSVs.",
    )
    return parser.parse_args()


def load_and_filter(
    df_path: str, start_date: str, end_date: str, logger: logging.Logger
) -> pd.DataFrame:
    """Load dataset and filter by valid_datetime_start date range."""
    df = pd.read_csv(df_path)
    if "valid_datetime_start" not in df.columns:
        raise ValueError("Dataset must contain 'valid_datetime_start' column.")

    df["valid_datetime_start"] = pd.to_datetime(
        df["valid_datetime_start"], errors="coerce"
    )
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    filtered = df[df["valid_datetime_start"].between(start_dt, end_dt)].copy()
    logger.info(
        f"Filtered to {len(filtered):,} rows for date range {start_date} to {end_date}"
    )
    assert isinstance(filtered, pd.DataFrame), "Filtered must be a DataFrame"

    return filtered


def generate_output_paths(
    base_path: str, start_date: str, end_date: str, suffix: str
) -> str:
    """Generate output path with date range suffix, removing existing date range from base name.

    Parameters
    ----------
    base_path : str
        Input CSV path.
    start_date : str
        Start date (YYYY-MM-DD).
    end_date : str
        End date (YYYY-MM-DD).
    suffix : str
        Suffix like '_train' or '_test'.
    """
    base_name = os.path.basename(base_path).replace(".csv", "")
    # Remove trailing date range if present (e.g., _20230106_20250206)
    base_name = re.sub(r"_(\d{8})_(\d{8})$", "", base_name)
    date_suffix = f"{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    return os.path.join(
        os.path.dirname(base_path), f"{base_name}_{date_suffix}{suffix}.csv"
    )


def main() -> None:
    args = parse_args()

    # Validate date ranges don't overlap
    train_start = pd.to_datetime(args.train_start)
    train_end = pd.to_datetime(args.train_end)
    test_start = pd.to_datetime(args.test_start)
    test_end = pd.to_datetime(args.test_end)
    if train_start <= test_end and test_start <= train_end:
        logger.error("Train and test date ranges overlap.")
        sys.exit(1)

    try:
        # Load and filter
        train_df = load_and_filter(
            args.dataset_csv, args.train_start, args.train_end, logger
        )
        test_df = load_and_filter(
            args.dataset_csv, args.test_start, args.test_end, logger
        )

        # Generate output paths
        train_output = generate_output_paths(
            args.dataset_csv, args.train_start, args.train_end, "_train"
        )
        test_output = generate_output_paths(
            args.dataset_csv, args.test_start, args.test_end, "_test"
        )

        # Write
        os.makedirs(args.output_dir, exist_ok=True)
        train_df.to_csv(train_output, index=False)
        test_df.to_csv(test_output, index=False)
        logger.info(
            f"Train set written to {train_output} ({len(train_df)} rows)"
        )
        logger.info(f"Test set written to {test_output} ({len(test_df)} rows)")

    except Exception as e:
        logger.exception(f"Dataset split failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
