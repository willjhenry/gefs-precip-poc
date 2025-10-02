from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

# Ensure runtime base uses /tmp/hydro unless overridden
os.environ.setdefault("HYDRO_RUNTIME_BASE_DIR", "/tmp/hydro")

# Predict function lives in scripts package
from hydro.predict_live import run_prediction  # noqa: E402


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler returning live prediction as JSON.

    Expected query parameters (API Gateway HTTP API style):
    - tag: optional artifacts tag
    - meta: optional explicit meta path (if packaged inside image)
    - step: lead step hours (default 3)
    - test_mode: "true"/"false" (default true for POC)
    - forecast_date: YYYY-MM-DD
    - cycle: 00/06/12/18
    """
    params = event.get("queryStringParameters") or {}
    tag = params.get("tag")
    meta = params.get("meta")
    step = int(params.get("step", 3))
    test_mode = str(params.get("test_mode", "true")).lower() != "false"
    forecast_date = params.get("forecast_date")
    cycle = params.get("cycle")

    try:
        df: pd.DataFrame = run_prediction(
            tag=tag,
            meta=meta,
            step=step,
            test_mode=test_mode,
            forecast_date=forecast_date,
            cycle=cycle,
        )
        # Return the first row (POC) as JSON
        body = df.head(1).to_dict(orient="records")[0]
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, default=str),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
