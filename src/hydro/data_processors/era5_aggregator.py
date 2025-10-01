from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from hydro.common import (
    PROCESSED_DIR,
    build_era5_basename,
    build_era5_processed_dir,
)


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

    - For variable "tp": daily sum (assumes input is already in mm)
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

        base_filename = os.path.basename(input_csv)
        variable = self._infer_variable_from_filename(base_filename)
        if variable not in {"tp", "t2m"}:
            raise ValueError(
                f"Unsupported variable inferred from filename: '{variable}'. Expected 'tp' or 't2m'."
            )
        # Parse location from filename
        lat, lon = self._parse_location_from_filename(base_filename)

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

        daily["valid_datetime_start"] = pd.to_datetime(daily["day"])
        daily["valid_datetime_end"] = pd.to_datetime(
            daily["day"]
        ) + pd.Timedelta(days=1)

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

        # Build output path using standardized helpers
        processed_dir = build_era5_processed_dir((lat, lon), variable, "daily")
        os.makedirs(processed_dir, exist_ok=True)

        base = build_era5_basename(variable, "daily", (lat, lon))

        # Compute start/end once; reuse for filename and metadata
        start_dt = out_df["valid_datetime_start"].min()
        end_dt = out_df["valid_datetime_end"].max()
        date_range_str = f"{start_dt.strftime('%Y%m%d')}-{(end_dt - pd.Timedelta(seconds=1)).strftime('%Y%m%d')}"

        out_filename = f"{base}_{date_range_str}.csv"
        output_path = os.path.join(processed_dir, out_filename)

        # convert valid_datetime_start and valid_datetime_end to strings of
        # format YYYY-MM-DD HH:MM:SS
        out_df["valid_datetime_start"] = out_df[
            "valid_datetime_start"
        ].dt.strftime("%Y-%m-%d %H:%M:%S")
        out_df["valid_datetime_end"] = out_df[
            "valid_datetime_end"
        ].dt.strftime("%Y-%m-%d %H:%M:%S")

        out_df.to_csv(output_path, index=False)
        self.logger.info(
            f"Wrote daily aggregation for {variable}: {output_path} ({len(out_df)} days)"
        )

        return Era5DailyAggregationResult(
            output_path=output_path,
            variable=variable,
            num_days=len(out_df),
            start_datetime=start_dt,  # type: ignore
            end_datetime=end_dt,  # type: ignore
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

    @staticmethod
    def _parse_location_from_filename(filename: str) -> tuple[float, float]:
        """Parse lat/lon from filename using lat-..._lon-... pattern.

        Parameters
        ----------
        filename
            Basename of the file.

        Returns
        -------
        tuple[float, float]
            (lat, lon) parsed from filename.

        Raises
        ------
        ValueError
            If lat/lon cannot be parsed.
        """
        m = re.search(r"lat-([0-9p-]+)_lon-([0-9p-]+)", filename)
        if m:
            lat_str, lon_str = m.groups()
            lat = float(lat_str.replace("p", "."))
            lon = float(lon_str.replace("p", "."))
            return lat, lon
        raise ValueError(f"Could not parse lat/lon from filename: {filename}")
