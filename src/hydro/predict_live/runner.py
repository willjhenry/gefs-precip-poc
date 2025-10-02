from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import joblib
import pandas as pd

from hydro.common import (
    MODEL_ARTIFACTS_DIR,
    align_columns,
    build_forecast_hours,
    find_latest_meta_under_tag_dirs,
    s3_object_exists,
    tag_from_meta_path,
)
from hydro.data_processors.dataset_assembler import DatasetAssembler
from hydro.data_processors.gefs_aggregator import GefsAggregator
from hydro.data_processors.gefs_downloader import GEFSDownloader

logger = logging.getLogger(__name__)


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
    tag: str | None, meta: str | None
) -> tuple[str, str, str, list[str], dict[str, Any]]:
    """Resolve paths and meta for model, scaler, and pred_cols."""
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
        meta_obj: dict[str, Any] = json.load(f)

    pred_cols: list[str] = list(meta_obj.get("pred_cols", []))
    inferred_tag = tag_from_meta_path(meta_path)
    base_dir = os.path.dirname(meta_path)
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


def find_latest_gefs_date_cycle(
    lead_start: int, cycle_hint: str | None = None
) -> tuple[str, str]:
    """Find latest available (forecast_date, cycle) on GEFS S3."""
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


def run_prediction(
    tag: str | None,
    meta: str | None,
    step: int = 3,
    test_mode: bool = True,
    forecast_date: str | None = None,
    cycle: str | None = None,
) -> pd.DataFrame:
    """Run end-to-end live prediction and return a prediction DataFrame."""
    model_path, scaler_path, meta_path, pred_cols, meta_obj = (
        resolve_artifacts(tag, meta)
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
    forecast_hours = build_forecast_hours(lead_start, lead_end, step)

    # Resolve forecast_date and cycle strictly from GEFS availability or user input
    if forecast_date is None and cycle is None:
        forecast_date, cycle = find_latest_gefs_date_cycle(
            lead_start=lead_start
        )
    elif forecast_date is None:
        # User provided cycle; find latest date that has this cycle
        forecast_date, detected_cycle = find_latest_gefs_date_cycle(
            lead_start=lead_start, cycle_hint=cycle
        )
        cycle = cycle or detected_cycle
    elif cycle is None:
        # User provided date; find latest available cycle on that date
        ymd = forecast_date.replace("-", "")
        cycle_order = ["18", "12", "06", "00"]
        resolved_cycle: str | None = None
        for cyc in cycle_order:
            filename = f"geavg.t{cyc}z.pgrb2s.0p25.f{lead_start:03d}"
            key = (
                f"gefs.{ymd}/{cyc}/{GEFSDownloader.FORECAST_MODEL}/{filename}"
            )
            if s3_object_exists(GEFSDownloader.GEFS_BUCKET, key):
                resolved_cycle = cyc
                break
        cycle = resolved_cycle or "00"

    logger.info(
        f"Using artifacts: model={os.path.basename(model_path)}, scaler={os.path.basename(scaler_path)}, meta={os.path.basename(meta_path)}"
    )
    logger.info(
        f"Config: location={location}, lead={lead_start}-{lead_end}, forecast_date={forecast_date}, cycle={cycle}"
    )

    downloader = GEFSDownloader(
        start_date=forecast_date,
        end_date=forecast_date,
        location=location,
        cycle=cycle,
        forecast_hours=forecast_hours,
        logger=logger,
        test=test_mode,
    )
    downloader.download(resume=False)
    per_hour_csv = downloader.output_file

    aggregator = GefsAggregator(
        input_csv=per_hour_csv,
        start_hour=lead_start,
        end_hour=lead_end,
        step=step,
        logger=logger,
    )
    aggregator.aggregate()
    agg_csv = aggregator.output_csv
    if not agg_csv:
        raise RuntimeError("Aggregator did not set output_csv")

    assembler = DatasetAssembler(logger=logger)
    gefs_df = assembler.process_gefs_columns([agg_csv])
    gefs_df = assembler.add_monthly_indicator_columns(gefs_df)
    if "bias" not in gefs_df.columns:
        gefs_df["bias"] = 1.0

    gefs_df = align_columns(gefs_df, pred_cols, fill_value=0.0, dtype=float)
    X = gefs_df.loc[:, pred_cols].values
    scaler = joblib.load(scaler_path)
    X_scaled = scaler.transform(X)
    keras_mod = importlib.import_module("tensorflow.keras")
    model = keras_mod.models.load_model(model_path, compile=False)
    gamma_params = model.predict(X_scaled)
    k = gamma_params[:, 0]
    beta = gamma_params[:, 1]
    pred_mean = (k / beta).astype(float)

    if "valid_datetime_end" in gefs_df.columns:
        valid_end_series = gefs_df["valid_datetime_end"].astype(str)
    else:
        valid_end_series = pd.Series([None] * len(gefs_df), dtype=object)
    out_df = pd.DataFrame(
        {
            "forecast_date": gefs_df["forecast_date"].astype(str),
            "cycle": cycle,
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
    # Include the resolved cycle so callers can use it for naming
    out_df["cycle"] = cycle
    return out_df
