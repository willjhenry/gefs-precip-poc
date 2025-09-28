from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from hydro.common import PROCESSED_DIR


@dataclass
class Era5DailyAggregationResult:
    """Container for an aggregated ERA5 daily output."""

    output_path: str
    variable: str
    num_days: int
    start_datetime: pd.Timestamp
    end_datetime: pd.Timestamp


class Era5DailyAggregator:
    """Aggregate hourly ERA5 CSVs to daily statistics.

    - For variable "tp": daily sum, converted from meters (m) to millimeters (mm)
      by multiplying by 1000 to align with GEFS (kg m^-2 ≡ mm)
    - For variable "t2m": daily min, mean, max

    Methods return the path to the aggregated CSV written to PROCESSED_DIR.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.processed_dir = PROCESSED_DIR
        os.makedirs(self.processed_dir, exist_ok=True)

    def aggregate_file(self, input_csv: str) -> Era5DailyAggregationResult:
        """Aggregate a single ERA5 hourly CSV to daily output.

        Parameters
        ----------
        input_csv
            Absolute path to the input ERA5 hourly CSV containing columns
            'valid_time' and 'value'. The filename should include the variable
            (e.g., 'era5_tp_*.csv' or 'era5_t2m_*.csv').

        Returns
        -------
        Era5DailyAggregationResult
            Metadata about the aggregated output written to disk.
        """
        if not os.path.exists(input_csv):
            raise FileNotFoundError(f"Input CSV not found: {input_csv}")

        variable = self._infer_variable_from_filename(
            os.path.basename(input_csv)
        )
        if variable not in {"tp", "t2m"}:
            raise ValueError(
                f"Unsupported variable inferred from filename: '{variable}'. Expected 'tp' or 't2m'."
            )

        df = pd.read_csv(input_csv)
        if "valid_time" not in df.columns or "value" not in df.columns:
            raise ValueError(
                "Input CSV must contain 'valid_time' and 'value' columns."
            )

        time_series = pd.to_datetime(df["valid_time"], errors="coerce")
        values = pd.to_numeric(df["value"], errors="coerce")
        base_df = pd.DataFrame(
            {"valid_time": time_series, "value": values}
        ).dropna()
        if base_df.empty:
            raise ValueError(
                "No valid rows after parsing 'valid_time' and 'value'."
            )

        # Floor to daily boundaries (UTC assumed)
        base_df["day"] = base_df["valid_time"].dt.floor("D")

        if variable == "tp":
            daily = (
                base_df.groupby("day")["value"].sum(min_count=1).reset_index()
            )
            daily = daily.rename(columns={"value": "tp"})
            # Convert from meters to millimeters to match GEFS units (mm)
            daily["tp"] = pd.to_numeric(daily["tp"], errors="coerce") * 1000.0
        else:  # t2m
            agg_df = (
                base_df.groupby("day")["value"]
                .agg(["min", "mean", "max"])
                .reset_index()
            )
            daily = agg_df.rename(
                columns={
                    "min": "t2m_min",
                    "mean": "t2m_mean",
                    "max": "t2m_max",
                }
            )

        daily["valid_datetime_start"] = daily["day"]
        daily["valid_datetime_end"] = daily["day"] + pd.Timedelta(days=1)

        # Reorder columns
        if variable == "tp":
            output_cols = [
                "valid_datetime_start",
                "valid_datetime_end",
                "tp",
            ]
        else:
            output_cols = [
                "valid_datetime_start",
                "valid_datetime_end",
                "t2m_min",
                "t2m_mean",
                "t2m_max",
            ]
        out_df = daily[output_cols].sort_values("valid_datetime_start")

        # Build output path
        date_start = out_df["valid_datetime_start"].min()
        date_end = out_df["valid_datetime_end"].max() - pd.Timedelta(seconds=1)
        date_range_str = (
            f"{date_start.strftime('%Y%m%d')}_{date_end.strftime('%Y%m%d')}"
        )

        grid_suffix = self._extract_grid_suffix(os.path.basename(input_csv))
        var_tag = f"era5_{variable}_daily"
        filename_parts: List[str] = [var_tag]
        if grid_suffix:
            filename_parts.append(grid_suffix)
        filename_parts.append(date_range_str)
        out_filename = "_".join(filename_parts) + ".csv"
        output_path = os.path.join(self.processed_dir, out_filename)

        out_df.to_csv(output_path, index=False)
        self.logger.info(
            f"Wrote daily aggregation for {variable}: {output_path} ({len(out_df)} days)"
        )

        return Era5DailyAggregationResult(
            output_path=output_path,
            variable=variable,
            num_days=len(out_df),
            start_datetime=out_df["valid_datetime_start"].min(),
            end_datetime=out_df["valid_datetime_end"].max(),
        )

    @staticmethod
    def _infer_variable_from_filename(filename: str) -> str:
        """Infer variable ('tp' or 't2m') from filename.

        Parameters
        ----------
        filename
            Basename of the file.

        Returns
        -------
        str
            'tp' or 't2m' if detected, otherwise the part after 'era5_'.
        """
        m = re.search(r"era5_(tp|t2m)", filename)
        if m:
            return m.group(1)
        # Fallback: try to guess conservatively
        if "t2m" in filename:
            return "t2m"
        if "tp" in filename:
            return "tp"
        return "unknown"

    @staticmethod
    def _extract_grid_suffix(filename: str) -> str:
        """Extract the grid point suffix from filename, e.g., '(47p5,8p0)'.

        Parameters
        ----------
        filename
            Basename of the file.

        Returns
        -------
        str
            The grid point string if found, else empty string.
        """
        m = re.search(r"(\(-?\d+p\d,\-?\d+p\d\))", filename)
        return m.group(1) if m else ""
