#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import re
import sys

import pandas as pd

from hydro.common import SCRIPTS_DIR

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


def generate_output_path(
    base_path: str,
    df: pd.DataFrame,
    prefix: str,
    fallback_start: str | None = None,
    fallback_end: str | None = None,
) -> str:
    """Generate output path in same directory with prefix and actual date range.

    The filename is constructed as:
        <prefix>_<base_name_without_date>_<YYYYMMDD-YYYYMMDD>.csv

    If ``df`` has no valid dates, falls back to provided ``fallback_start`` and
    ``fallback_end`` (expected format YYYY-MM-DD). Any existing trailing date
    suffix in ``base_path`` is removed before composing the new name.

    Parameters
    ----------
    base_path : str
        Input CSV path.
    df : pd.DataFrame
        Split dataframe containing 'valid_datetime_start'.
    prefix : str
        File prefix, e.g., 'train' or 'test'.
    fallback_start : str | None
        Optional fallback start date (YYYY-MM-DD).
    fallback_end : str | None
        Optional fallback end date (YYYY-MM-DD).

    Returns
    -------
    str
        Output path.
    """

    base_dir = os.path.dirname(base_path)
    stem, ext = os.path.splitext(os.path.basename(base_path))
    # Strip trailing date range if present (supports '_' or '-')
    stem = re.sub(r"_(\d{8})[-_](\d{8})$", "", stem)

    start_str: str | None = None
    end_str: str | None = None
    if "valid_datetime_start" in df.columns and not df.empty:
        dates = pd.to_datetime(df["valid_datetime_start"], errors="coerce")
        if not dates.isna().all():
            start_str = dates.min().strftime("%Y%m%d")
            end_str = dates.max().strftime("%Y%m%d")

    if start_str is None or end_str is None:
        if fallback_start and fallback_end:
            start_str = fallback_start.replace("-", "")
            end_str = fallback_end.replace("-", "")
        else:
            # As a last resort, omit the date range
            return os.path.join(base_dir, f"{prefix}_{stem}{ext}")

    return os.path.join(
        base_dir, f"{prefix}_{stem}_{start_str}-{end_str}{ext}"
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

        # Generate output paths using actual date ranges in each split
        train_output = generate_output_path(
            args.dataset_csv,
            train_df,
            "train",
            None,
            None,
        )
        test_output = generate_output_path(
            args.dataset_csv,
            test_df,
            "test",
            None,
            None,
        )

        # Write
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
