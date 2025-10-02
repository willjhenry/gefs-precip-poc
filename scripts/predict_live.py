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
import importlib  # noqa: F401 (kept for compatibility)
import json
import logging
import os
import sys
from datetime import (
    datetime,  # noqa: F401 (imported for future timestamping if needed)
)

# Note: heavy runtime is encapsulated in hydro.predict_live.runner
from hydro.common import (
    SCRIPTS_DIR,
    build_live_prediction_filename,
    build_live_predictions_dir,
    utc_timestamp,
)
from hydro.predict_live.runner import resolve_artifacts, run_prediction

# Logging (safe for read-only environments)
LOG_FILE = os.path.join(SCRIPTS_DIR, "predict_live.log")
handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
try:
    log_dir = os.path.dirname(LOG_FILE)
    if os.access(log_dir, os.W_OK):
        handlers.insert(0, logging.FileHandler(LOG_FILE))
except Exception:
    # Fallback to stdout-only if file handler cannot be created
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=handlers,
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


# Back-compat shims removed: import directly from hydro.predict_live.runner above


pass


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


def find_latest_gefs_date_cycle(*args, **kwargs):  # type: ignore[no-redef]
    from hydro.predict_live.runner import find_latest_gefs_date_cycle as _find

    return _find(*args, **kwargs)


def main() -> None:
    args = parse_args()

    out_df = run_prediction(
        tag=args.tag,
        meta=args.meta,
        step=args.step,
        test_mode=args.test_mode,
        forecast_date=args.forecast_date,
        cycle=args.cycle,
    )

    # 5) Persist & print
    # Derive model tag from meta path for output dir naming
    # Re-resolve to obtain meta path
    _, _, meta_path, _, _ = resolve_artifacts(args.tag, args.meta)
    model_tag = (
        os.path.basename(meta_path).replace("meta_", "").replace(".json", "")
    )
    # Infer location/lead window from output df context is not simple here,
    # so reuse meta for naming directories
    # For simplicity, use placeholders from meta for directory building
    meta_obj = json.load(open(meta_path))
    grid_point = meta_obj.get("grid_point") or meta_obj.get("location")
    location: tuple[float, float] = (
        float(grid_point[0]),
        float(grid_point[1]),
    )
    lead_start, lead_end = map(int, meta_obj.get("lead_range", [0, 0]))
    # We need cycle for filename; prefer resolved cycle from output
    cycle_val = None
    if "cycle" in out_df.columns and not out_df.empty:
        try:
            cycle_val = str(out_df["cycle"].iloc[0])
        except Exception:
            cycle_val = None
    if not cycle_val:
        cycle_val = "00"
    out_dir = build_output_base_dir(location, lead_start, lead_end, model_tag)
    if args.output:
        out_path = args.output
    else:
        out_path = build_output_path(
            out_dir, location, lead_start, lead_end, cycle_val, fmt=args.format
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
