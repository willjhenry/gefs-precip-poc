#!/usr/bin/env python3
"""
Live prediction script: download GEFS, aggregate, build predictors, and run a
saved TensorFlow model to produce precipitation predictions.

Defaults are read from the model's meta JSON in `MODEL_ARTIFACTS_DIR` (grid
point, lead range, and `pred_cols`). CLI arguments are minimal and only used to
override as needed. If `--forecast-date` and `--cycle` are omitted, the script
auto-detects the most recent available GEFS date/cycle.

DRY: Reuses existing classes:
- hydro.data_processors.GEFSDownloader
- hydro.data_processors.GefsAggregator
- hydro.data_processors.DatasetAssembler (feature pivot + stats + month dummies)

Outputs a CSV/JSON with predictions in the same processed tree.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import joblib
import pandas as pd

from hydro.common import (
    MODEL_ARTIFACTS_DIR,
    SCRIPTS_DIR,
    align_columns,
    build_forecast_hours,
    build_live_prediction_filename,
    build_live_predictions_dir,
    find_latest_meta_under_tag_dirs,
    s3_object_exists,
    tag_from_meta_path,
    utc_timestamp,
)
from hydro.data_processors.dataset_assembler import DatasetAssembler
from hydro.data_processors.gefs_aggregator import GefsAggregator
from hydro.data_processors.gefs_downloader import GEFSDownloader

# Logging
LOG_FILE = os.path.join(SCRIPTS_DIR, "predict_live.log")
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
        description="Live inference using saved TF model and latest GEFS data",
    )
    parser.add_argument(
        "--forecast-date",
        type=str,
        default=None,
        help="Forecast date (YYYY-MM-DD). If omitted, latest available is used.",
    )
    parser.add_argument(
        "--cycle",
        type=str,
        default=None,
        help="GEFS cycle (00/06/12/18). If omitted with no date, auto-detect latest.",
    )
    parser.add_argument("--step", type=int, default=3, help="Lead step hours")
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Artifacts tag to load from MODEL_ARTIFACTS_DIR (optional)",
    )
    parser.add_argument(
        "--meta", type=str, default=None, help="Path to meta .json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional explicit output file path (.csv or .json)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "json"],
        default="csv",
        help="Output format if --output is provided (default csv)",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Use limited members and minimal dates for a fast test run",
    )
    return parser.parse_args()


def _find_latest(path: str, pattern_suffix: str) -> str | None:
    candidates = [
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.endswith(pattern_suffix)
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def resolve_artifacts(
    tag: str | None,
    meta: str | None,
) -> tuple[str, str, str, list[str], dict]:
    """Resolve paths and meta for model, scaler, and pred_cols.

    Returns
    -------
    (model_path, scaler_path, meta_path, pred_cols, meta_obj)
    """
    # Resolve meta path: explicit, tag in subdir or top-level, or newest recursively
    if meta:
        meta_path = meta
    elif tag:
        meta_path = os.path.join(MODEL_ARTIFACTS_DIR, tag, f"meta_{tag}.json")
    else:
        meta_path = find_latest_meta_under_tag_dirs(MODEL_ARTIFACTS_DIR)
    if not meta_path or not os.path.exists(meta_path):
        raise FileNotFoundError(
            "Meta file not found. Provide --meta or a valid --tag."
        )

    with open(meta_path, "r") as f:
        meta_obj = json.load(f)

    pred_cols: list[str] = list(meta_obj.get("pred_cols", []))
    inferred_tag = tag_from_meta_path(meta_path)
    base_dir = os.path.dirname(meta_path)
    # Require artifacts next to meta (no top-level fallback)
    model_path = (
        os.path.join(base_dir, f"model_{inferred_tag}.keras")
        if inferred_tag
        else None
    )
    scaler_path = (
        os.path.join(base_dir, f"scaler_{inferred_tag}.joblib")
        if inferred_tag
        else None
    )

    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(
            "Model file not found matching meta tag. Provide --model or --tag."
        )
    if not scaler_path or not os.path.exists(scaler_path):
        raise FileNotFoundError(
            "Scaler file not found matching meta tag. Provide --scaler or --tag."
        )

    return model_path, scaler_path, meta_path, pred_cols, meta_obj


def build_output_base_dir(
    location: tuple[float, float],
    lead_start: int,
    lead_end: int,
    model_tag: str,
) -> str:
    out_dir = build_live_predictions_dir(
        model_tag, location, lead_start, lead_end
    )
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def build_output_path(
    out_dir: str,
    location: tuple[float, float],
    lead_start: int,
    lead_end: int,
    cycle: str,
    fmt: str,
) -> str:
    ts = utc_timestamp()
    filename = build_live_prediction_filename(
        location=location,
        lead_start=lead_start,
        lead_end=lead_end,
        cycle=cycle,
        timestamp_utc=ts,
        fmt=fmt,
    )
    return os.path.join(out_dir, filename)


def find_latest_gefs_date_cycle(
    lead_start: int, cycle_hint: str | None = None
) -> tuple[str, str]:
    """Find latest available (forecast_date, cycle) on GEFS S3.

    Tries recent days and cycles (18,12,06,00) unless a cycle hint is provided.
    """
    cycles = [cycle_hint] if cycle_hint else ["18", "12", "06", "00"]
    now = datetime.now(timezone.utc)
    for days_back in range(0, 7):
        dt = now - timedelta(days=days_back)
        ymd = dt.strftime("%Y%m%d")
        for cyc in cycles:
            filename = f"geavg.t{cyc}z.pgrb2s.0p25.f{lead_start:03d}"
            key = (
                f"gefs.{ymd}/{cyc}/{GEFSDownloader.FORECAST_MODEL}/{filename}"
            )
            if s3_object_exists(GEFSDownloader.GEFS_BUCKET, key):
                return dt.strftime("%Y-%m-%d"), cyc
    return now.strftime("%Y-%m-%d"), (cycle_hint or "00")


def main() -> None:
    args = parse_args()

    # Resolve artifacts and meta-driven config
    model_path, scaler_path, meta_path, pred_cols, meta_obj = (
        resolve_artifacts(args.tag, args.meta)
    )
    grid_point = meta_obj.get("grid_point") or meta_obj.get("location")
    if not grid_point or len(grid_point) != 2:
        raise ValueError("Meta file must include 'grid_point': [lat, lon]")
    location: tuple[float, float] = (
        float(grid_point[0]),
        float(grid_point[1]),
    )
    lead_range = meta_obj.get("lead_range")
    if not lead_range or len(lead_range) != 2:
        raise ValueError("Meta file must include 'lead_range': [start, end]")
    lead_start: int = int(lead_range[0])
    lead_end: int = int(lead_range[1])
    forecast_hours = build_forecast_hours(lead_start, lead_end, args.step)

    # Determine forecast date and cycle (CLI overrides meta or auto-detection)
    forecast_date_arg = args.forecast_date
    cycle_arg = args.cycle
    meta_cycle = meta_obj.get("cycle")
    if forecast_date_arg is None and cycle_arg is None:
        forecast_date, cycle = find_latest_gefs_date_cycle(
            lead_start=lead_start
        )
    elif forecast_date_arg is None:
        forecast_date, _ = find_latest_gefs_date_cycle(
            lead_start=lead_start, cycle_hint=cycle_arg
        )
        cycle = cycle_arg or (meta_cycle or "00")
    else:
        forecast_date = forecast_date_arg
        cycle = cycle_arg or (meta_cycle or "00")

    logger.info(
        f"Using artifacts: model={os.path.basename(model_path)}, scaler={os.path.basename(scaler_path)}, meta={os.path.basename(meta_path)}"
    )
    logger.info(
        f"Config: location={location}, lead={lead_start}-{lead_end}, forecast_date={forecast_date}, cycle={cycle}"
    )

    # 1) Download GEFS for the provided forecast date
    downloader = GEFSDownloader(
        start_date=forecast_date,
        end_date=forecast_date,
        location=location,
        cycle=cycle,
        forecast_hours=forecast_hours,
        logger=logger,
        test=args.test_mode,
    )
    downloader.download(resume=False)
    per_hour_csv = downloader.output_file
    logger.info(f"Per-hour GEFS saved: {per_hour_csv}")

    # 2) Aggregate over the lead window
    aggregator = GefsAggregator(
        input_csv=per_hour_csv,
        start_hour=lead_start,
        end_hour=lead_end,
        step=args.step,
        logger=logger,
    )
    aggregator.aggregate()
    agg_csv = aggregator.output_csv
    if not agg_csv:
        raise RuntimeError("Aggregator did not set output_csv")
    logger.info(f"Aggregated GEFS saved: {agg_csv}")

    # 3) Build predictor row(s) using DatasetAssembler utilities
    assembler = DatasetAssembler(logger=logger)
    # Reuse the same transformations used for training (pivot + ensemble stats)
    gefs_df = assembler.process_gefs_columns([agg_csv])
    # Month dummies
    gefs_df = assembler.add_monthly_indicator_columns(gefs_df)
    # Bias column
    if "bias" not in gefs_df.columns:
        gefs_df["bias"] = 1.0

    # Align columns to pred_cols using shared helper
    gefs_df = align_columns(gefs_df, pred_cols, fill_value=0.0, dtype=float)
    X = gefs_df.loc[:, pred_cols].values

    # 4) Inference
    scaler = joblib.load(scaler_path)
    X_scaled = scaler.transform(X)
    # Dynamic import to avoid linter issues with tf.keras in some stub sets
    keras_mod = importlib.import_module("tensorflow.keras")
    # Load without compiling to avoid needing custom loss/metrics at load time
    model = keras_mod.models.load_model(model_path, compile=False)
    gamma_params = model.predict(X_scaled)
    # Assume (shape=k, rate=beta) > 0
    k = gamma_params[:, 0]
    beta = gamma_params[:, 1]
    pred_mean = (k / beta).astype(float)

    # Compose output frame (one row per forecast_date)
    if "valid_datetime_end" in gefs_df.columns:
        valid_end_series = gefs_df["valid_datetime_end"].astype(str)
    else:
        valid_end_series = pd.Series([None] * len(gefs_df), dtype=object)
    out_df = pd.DataFrame(
        {
            "forecast_date": gefs_df["forecast_date"].astype(str),
            "valid_datetime_start": gefs_df["valid_datetime_start"].astype(
                str
            ),
            "valid_datetime_end": valid_end_series,
            "lead_hours_range": gefs_df["lead_hours_range"],
            "gamma_shape": k,
            "gamma_rate": beta,
            "prediction_mean": pred_mean,
        }
    )

    # 5) Persist & print
    model_tag = (
        os.path.basename(meta_path).replace("meta_", "").replace(".json", "")
    )
    out_dir = build_output_base_dir(location, lead_start, lead_end, model_tag)
    if args.output:
        out_path = args.output
    else:
        out_path = build_output_path(
            out_dir, location, lead_start, lead_end, cycle, fmt=args.format
        )

    if args.format == "json" or out_path.endswith(".json"):
        out_df.to_json(out_path, orient="records", date_format="iso")
    else:
        out_df.to_csv(out_path, index=False)
    logger.info(f"Wrote predictions to {out_path}")

    # Echo first row to console for convenience
    try:
        print(json.dumps(out_df.iloc[0].to_dict(), default=str))
    except Exception:
        # Fallback to CSV-style string
        print(out_df.head(1).to_string(index=False))


if __name__ == "__main__":
    main()
