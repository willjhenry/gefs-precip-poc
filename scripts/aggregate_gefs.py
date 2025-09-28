"""
Aggregate GEFS total precipitation (tp) for specified lead hours by forecast date and member.

This script uses the GefsAggregator class to read the per-hour tp extraction CSV produced by
`scripts/download_gefs_ensemble.py` and compute sums across the specified lead hours
(e.g., 120–168, 3-hourly steps) for each `(forecast_date, ensemble_member)` pair.

The output CSV includes one row per `(forecast_date, member)` with:
- forecast_date
- member
- valid_datetime_start (first valid time in window)
- valid_datetime_range (start to end times)
- lead_hours_range (e.g., "120-168")
- tp (sum of tp over window)

Examples
--------
Run with defaults (120-168 hours, input from data/processed/gefs_ensemble_tp.csv):
    python scripts/aggregate_gefs_tp_120_168.py

Specify input and custom hours:
    python scripts/aggregate_gefs_tp_120_168.py \
        --input-csv data/processed/gefs_ensemble_tp.csv \
        --start-hour 120 --end-hour 168 --step 3 \
        --output-csv data/processed/gefs_ensemble_tp_120_168.csv
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Tuple

from hydro.common import DATA_DIR, SCRIPTS_DIR
from hydro.data_processors.gefs_aggregator import GefsAggregator


def setup_paths() -> Tuple[str, str, str, str]:
    """Compute project paths.

    Returns
    -------
    tuple of str
        (scripts_dir, project_root, data_dir, processed_dir)
    """
    scripts_dir = SCRIPTS_DIR
    project_root = os.path.dirname(scripts_dir)
    data_dir = DATA_DIR
    processed_dir = os.path.join(data_dir, "processed")
    return scripts_dir, project_root, data_dir, processed_dir


def setup_logging(log_file: str) -> logging.Logger:
    """Configure a module-level logger.

    Parameters
    ----------
    log_file : str
        Path to the log file.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def parse_args(processed_dir: str) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    processed_dir : str
        Default processed directory for input/output.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Aggregate GEFS TP over lead hours using GefsAggregator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input-csv",
        type=str,
        default=os.path.join(processed_dir, "gefs_ensemble_tp.csv"),
        help="Path to input CSV from download_gefs_ensemble.py",
    )
    parser.add_argument(
        "--start-hour",
        type=int,
        default=120,
        help="Start lead hour (inclusive)",
    )
    parser.add_argument(
        "--end-hour",
        type=int,
        default=168,
        help="End lead hour (inclusive)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=3,
        help="Lead hour step",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=None,
        help="Path to write aggregated CSV (default: gefs_ensemble_tp_{start}-{end}.csv)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for CLI execution."""
    scripts_dir, project_root, data_dir, processed_dir = setup_paths()
    log_file = os.path.join(scripts_dir, "gefs_aggregate.log")
    logger = setup_logging(log_file)

    args = parse_args(processed_dir)

    # Compute default output if not provided
    if args.output_csv is None:
        args.output_csv = os.path.join(
            processed_dir,
            f"gefs_ensemble_tp_{args.start_hour}-{args.end_hour}.csv",
        )

    # Ensure output dir exists
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)

    try:
        aggregator = GefsAggregator(
            input_csv=args.input_csv,
            output_csv=args.output_csv,
            start_hour=args.start_hour,
            end_hour=args.end_hour,
            step=args.step,
            logger=logger,
        )
        aggregator.aggregate()
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Aggregation failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
