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
from typing import Iterable, List, Optional

import pandas as pd


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
        Ending lead hour (inclusive, default 168).
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
    """

    def __init__(
        self,
        input_csv: str,
        output_csv: str,
        start_hour: int = 120,
        end_hour: int = 168,
        step: int = 3,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.step = step
        self.logger = logger or logging.getLogger(__name__)

    def generate_lead_hours(self) -> List[int]:
        """
        Generate the list of lead hours for aggregation.

        Returns
        -------
        list of int
            Lead hours, e.g., [120, 123, ..., 168].
        """
        return list(range(self.start_hour, self.end_hour + 1, self.step))

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
        hours_list: List[int] = [int(h) for h in lead_hours]
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

        # Ensure output dir exists
        os.makedirs(os.path.dirname(self.output_csv), exist_ok=True)
        agg_df.to_csv(self.output_csv, index=False)
        self.logger.info(f"Wrote aggregated CSV to {self.output_csv}")
