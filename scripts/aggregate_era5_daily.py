#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import logging
import os
from typing import List

from hydro.data_processors.era5_aggregator import Era5DailyAggregator


def find_input_csvs(paths: List[str]) -> List[str]:
    resolved: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            resolved.extend(glob.glob(os.path.join(p, "*.csv")))
        elif os.path.isfile(p):
            resolved.append(p)
    # Keep only ERA5 CSVs we expect
    filtered = [f for f in resolved if os.path.basename(f).startswith("era5_")]
    return sorted(set(filtered))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate hourly ERA5 CSVs to daily outputs.\n"
            "- tp: sum per day\n- t2m: min/mean/max per day"
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help=(
            "One or more input CSV files or directories containing ERA5 hourly CSVs."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger("aggregate_era5_daily")

    inputs = find_input_csvs(args.inputs)
    if not inputs:
        logger.error("No ERA5 CSVs found in the provided inputs.")
        raise SystemExit(1)

    aggregator = Era5DailyAggregator(logger=logger)

    for csv_path in inputs:
        try:
            result = aggregator.aggregate_file(csv_path)
            logger.info(
                f"Aggregated {result.variable} -> {result.output_path} ({result.num_days} days)"
            )
        except Exception as e:
            logger.exception(f"Failed to aggregate {csv_path}: {e}")


if __name__ == "__main__":
    main()
