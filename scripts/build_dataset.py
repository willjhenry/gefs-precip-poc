#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys

from hydro.data_processors.dataset_assembler import DatasetAssembler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build merged dataset: GEFS (pivoted members) + ERA5 truth and lag-1 predictors."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--gefs-csv",
        type=str,
        action="append",
        default=None,
        help="Path(s) to GEFS aggregated CSV(s). Can be passed multiple times. If omitted, auto-detect all.",
    )
    parser.add_argument(
        "--era5-tp-daily",
        type=str,
        default=None,
        help="Path to ERA5 daily tp CSV (if omitted, auto-detect latest).",
    )
    parser.add_argument(
        "--era5-t2m-daily",
        type=str,
        default=None,
        help="Path to ERA5 daily t2m CSV (if omitted, auto-detect latest).",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=None,
        help="Path to write merged dataset (if omitted, auto-named in processed dir).",
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
    logger = logging.getLogger("build_dataset")

    assembler = DatasetAssembler(logger=logger)

    try:
        if args.gefs_csv and args.era5_tp_daily and args.era5_t2m_daily:
            gefs_csv = args.gefs_csv  # list of paths
            era5_tp_csv = args.era5_tp_daily
            era5_t2m_csv = args.era5_t2m_daily
        else:
            logger.info("Auto-detecting processed files...")
            gefs_csv, era5_tp_csv, era5_t2m_csv = assembler.find_inputs()
            logger.info(f"GEFS (count={len(gefs_csv)}): {gefs_csv}")
            logger.info(f"ERA5 TP daily: {era5_tp_csv}")
            logger.info(f"ERA5 T2M daily: {era5_t2m_csv}")

        result = assembler.assemble(
            gefs_csv=gefs_csv,
            era5_tp_daily_csv=era5_tp_csv,
            era5_t2m_daily_csv=era5_t2m_csv,
            output_csv=args.output_csv,
        )
        logger.info(
            f"Merged dataset written to {result.output_path} (rows={result.num_rows}, cols={result.num_columns})"
        )
    except Exception as e:
        logger.exception(f"Dataset build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
