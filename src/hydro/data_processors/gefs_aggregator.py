"""
GEFS Ensemble TP Aggregator.

Aggregates per-hour total precipitation from GEFS ensembles over specified lead
hours (e.g., 120-168) by forecast date and member, producing daily sums suitable
for modeling inputs.

The class reads the raw per-hour CSV (from GefsDownloader) and outputs a
summarized CSV with one row per (forecast_date, member) containing the summed
tp over the lead window, plus metadata on the aggregation range and valid times.
"""

import logging
import os
from collections.abc import Iterable

import pandas as pd

from hydro.common import (
    GRID_RHINE_POINT,
    build_gefs_basename,
    build_gefs_processed_dir,
    parse_cycle_from_name,
    parse_grid_from_name,
    parse_lead_range_from_name,
)


class GefsAggregator:
    """
    Aggregate GEFS total precipitation over a lead hour window by forecast date and member.

    Parameters
    ----------
    input_csv : str
        Path to input CSV from GefsDownloader (columns: forecast_date, ensemble_member,
        forecast_hour, tp, valid_time).
    output_csv : str
        Path to write aggregated CSV.
    start_hour : int, optional
        Starting lead hour (inclusive, default 120).
    end_hour : int, optional
        Ending lead hour (exclusive, default 168). Excluded because GEFS forecast hours
        represent 3-hour accumulations FROM that hour (e.g., f144 = 144-147 accumulation).
        To aggregate 120-144, use end_hour=144 which excludes f144.
    step : int, optional
        Step in hours between lead times (default 3).
    logger : logging.Logger, optional
        Logger instance.

    Notes
    -----
    - Assumes input data is 3-hourly accumulations; sums them for the window.
    - Handles empty inputs gracefully (returns empty DF with expected columns).
    - Output columns: forecast_date, member, valid_datetime_start, valid_datetime_range,
    lead_hours_range, tp (summed over window).
    - For a window 120-144, uses forecasts [120, 123, 126, 129, 132, 135, 138, 141]
      (excludes 144 since f144 represents accumulation for 144-147).
    """

    def __init__(
        self,
        input_csv: str,
        output_csv: str | None = None,
        start_hour: int = 120,
        end_hour: int = 168,
        step: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.step = step
        self.logger = logger or logging.getLogger(__name__)

    def _parse_input_metadata(
        self,
    ) -> tuple[tuple[float, float], int, int, str]:
        """
        Parse location, lead_start, lead_end, and cycle from input filename.

        Returns
        -------
        tuple[tuple[float, float], int, int, str]
            (location, lead_start, lead_end, cycle)
        """
        basename = os.path.basename(self.input_csv)
        # Grid
        grid = parse_grid_from_name(basename)
        # Lead
        lead = parse_lead_range_from_name(basename)
        # Cycle
        cycle = parse_cycle_from_name(basename) or "00"

        if grid:
            lat, lon = grid
        else:
            self.logger.warning(
                f"Could not parse grid from filename {basename}, using defaults"
            )
            lat = GRID_RHINE_POINT[0]
            lon = GRID_RHINE_POINT[1]

        if lead:
            lead_start, lead_end = lead
        else:
            self.logger.warning(
                f"Could not parse lead range from filename {basename}, using CLI defaults"
            )
            lead_start, lead_end = self.start_hour, self.end_hour

        return (lat, lon), lead_start, lead_end, cycle

    def generate_lead_hours(self) -> list[int]:
        """
        Generate the list of lead hours for aggregation.

        Returns
        -------
        list[int]
            Lead hours, e.g., [120, 123, ..., 141] for 120-144 window.

        Notes
        -----
        The end_hour is excluded because GEFS forecast hours represent 3-hour
        accumulations FROM that hour. For example, forecast hour 144 represents
        accumulation for 144-147, so to get precipitation for 120-144, we only
        use forecasts 120, 123, ..., 141.
        """
        return list(range(self.start_hour, self.end_hour, self.step))

    def read_input(self) -> pd.DataFrame:
        """
        Read and validate the input GEFS per-hour TP CSV.

        Returns
        -------
        pandas.DataFrame
            Parsed DataFrame with coerced dtypes.

        Raises
        ------
        ValueError
            If required columns are missing.
        """
        df = pd.read_csv(self.input_csv)
        self.logger.info(f"Read {len(df):,} rows from {self.input_csv}")

        # Ensure expected columns exist
        expected = {
            "forecast_date",
            "ensemble_member",
            "forecast_hour",
            "tp",
            "valid_time",
        }
        missing = expected.difference(df.columns)
        if missing:
            raise ValueError(f"Input CSV missing columns: {sorted(missing)}")

        # Coerce types
        df["forecast_hour"] = pd.to_numeric(
            df["forecast_hour"], errors="coerce"
        )
        df["tp"] = pd.to_numeric(df["tp"], errors="coerce")
        df["valid_time"] = pd.to_datetime(df["valid_time"], errors="coerce")

        return df

    def aggregate_tp(
        self, df: pd.DataFrame, lead_hours: Iterable[int]
    ) -> pd.DataFrame:
        """
        Aggregate tp over lead hours per (forecast_date, member).

        Parameters
        ----------
        df : pandas.DataFrame
            Input per-hour TP DataFrame.
        lead_hours : Iterable[int]
            Lead hours to sum (e.g., [120, 123, ..., 168]).

        Returns
        -------
        pandas.DataFrame
            Aggregated DataFrame with summed tp and metadata columns.
        """
        hours_list: list[int] = [int(h) for h in lead_hours]
        filtered = df[df["forecast_hour"].isin(hours_list)].copy()

        if filtered.empty:
            self.logger.warning(
                "No data in specified lead hours; returning empty DF"
            )
            cols = [
                "forecast_date",
                "member",
                "valid_datetime_start",
                "valid_datetime_range",
                "lead_hours_range",
                "tp",
            ]
            return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})

        grouped = (
            filtered.groupby(
                ["forecast_date", "ensemble_member"], dropna=False
            )
            .agg(
                tp=("tp", "sum"),
                valid_time_start=("valid_time", "min"),
                valid_time_end=("valid_time", "max"),
            )
            .reset_index()
        )

        grouped = grouped.rename(columns={"ensemble_member": "member"})

        # Format datetime fields
        valid_time_start_series: pd.Series = pd.to_datetime(
            grouped["valid_time_start"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")
        valid_time_end_series: pd.Series = pd.to_datetime(
            grouped["valid_time_end"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")
        grouped["valid_datetime_start"] = valid_time_start_series
        grouped["valid_datetime_range"] = (
            valid_time_start_series + " to " + valid_time_end_series
        )

        # Add lead hours range metadata
        lead_range_str = f"{self.start_hour}-{self.end_hour}"
        grouped["lead_hours_range"] = lead_range_str
        grouped["tp"] = grouped["tp"].round(
            4
        )  # Optional: round for readability

        # Ensure consistent column order
        result_columns = [
            "forecast_date",
            "member",
            "valid_datetime_start",
            "valid_datetime_range",
            "lead_hours_range",
            "tp",
        ]
        result_df: pd.DataFrame = grouped.loc[:, result_columns].copy()

        self.logger.info(
            f"Aggregated to {len(result_df):,} rows over {lead_range_str}"
        )
        return result_df

    def aggregate(self) -> None:
        """
        Main aggregation workflow: read input, aggregate, write output.

        Raises
        ------
        Exception
            If reading, aggregating, or writing fails.
        """
        lead_hours = self.generate_lead_hours()
        self.logger.info(
            f"Aggregating GEFS TP for lead hours {lead_hours[0]}–{lead_hours[-1]} "
            f"(step {self.step}, {len(lead_hours)} hours)"
        )

        df = self.read_input()
        agg_df = self.aggregate_tp(df, lead_hours)

        # Parse metadata from input filename (use only location and cycle)
        location, _lead_start, _lead_end, cycle = self._parse_input_metadata()

        # Build output directory based on CLI-provided lead window
        out_dir = build_gefs_processed_dir(
            location=location,
            lead_start=self.start_hour,
            lead_end=self.end_hour,
        )

        # Build sum basename using CLI lead window
        sum_basename = build_gefs_basename(
            kind="sum",
            location=location,
            lead_start=self.start_hour,
            lead_end=self.end_hour,
            cycle=cycle,
        )

        # Compute date range: min(valid_datetime_start) to max(valid_datetime_end) - 1 sec
        if not agg_df.empty and "valid_datetime_start" in agg_df.columns:
            # Parse the string datetime columns back to datetime objects
            start_datetimes = pd.to_datetime(
                agg_df["valid_datetime_start"], errors="coerce"
            )
            # Extract end datetimes from the valid_datetime_range column
            # Format: "YYYY-MM-DD HH:MM:SS to YYYY-MM-DD HH:MM:SS"
            end_datetime_strs = (
                agg_df["valid_datetime_range"].str.split(" to ").str[1]
            )
            end_datetimes = pd.to_datetime(end_datetime_strs, errors="coerce")

            # Get the range boundaries
            range_start = start_datetimes.min()
            range_end = end_datetimes.max() - pd.Timedelta(seconds=1)  # type: ignore # Subtract 1 second as per spec

            date_range_start = range_start.strftime("%Y%m%d")
            date_range_end = range_end.strftime("%Y%m%d")
            date_range_str = f"{date_range_start}-{date_range_end}"
        else:
            # Fallback
            date_range_str = "unknown-unknown"

        # Create final output path
        final_name = f"{sum_basename}_{date_range_str}.csv"
        auto_output_csv = os.path.join(out_dir, final_name)

        # Use explicit output_csv if provided, otherwise use auto-generated path
        final_output_csv = (
            self.output_csv if self.output_csv is not None else auto_output_csv
        )

        # Ensure output dir exists
        os.makedirs(os.path.dirname(final_output_csv), exist_ok=True)

        agg_df.to_csv(final_output_csv, index=False)
        self.logger.info(f"Wrote aggregated CSV to {final_output_csv}")

        # Update self.output_csv for compatibility
        self.output_csv = final_output_csv
