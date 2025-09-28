from __future__ import annotations

import glob
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from hydro.common import PROCESSED_DIR


@dataclass
class AssembledDataset:
    """Metadata for the assembled dataset output."""

    output_path: str
    num_rows: int
    num_gefs_columns: int


class DatasetAssembler:
    """Build a wide dataset from GEFS aggregated TP and ERA5 daily data.

    - Pivots GEFS members (control, perturbed, mean, spread) to columns
    - Joins ERA5 daily TP as truth on valid day window
    - Adds lag-1 ERA5 TP and t2m (min/mean/max) based on forecast date - 1 day
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.processed_dir = PROCESSED_DIR

    # ---------- Auto-discovery helpers ----------

    @staticmethod
    def _parse_date_range_from_name(
        filename: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        m = re.search(r"_(\d{8})_(\d{8})", filename)
        if not m:
            return None, None
        return m.group(1), m.group(2)

    @staticmethod
    def _parse_lead_range_from_name(filename: str) -> Optional[str]:
        # Support either ..._120-144.csv or ..._120-144_YYYYMMDD_YYYYMMDD.csv
        m = re.search(r"_(\d{2,3}-\d{2,3})(?:_|\.csv$)", filename)
        return m.group(1) if m else None

    @staticmethod
    def _extract_grid_suffix(filename: str) -> str:
        m = re.search(r"(\(-?\d+p\d,\-?\d+p\d\))", filename)
        return m.group(1) if m else ""

    def find_inputs(self) -> Tuple[List[str], str, str]:
        """Locate processed files for GEFS aggregated and ERA5 daily.

        Returns
        -------
        tuple
            (list_of_gefs_csvs, era5_tp_daily_csv, era5_t2m_daily_csv)
        """
        # GEFS aggregated (allow multiple matching files)
        candidates_gefs = glob.glob(
            os.path.join(self.processed_dir, "gefs_ensemble_tp*.csv")
        )
        candidates_gefs = [
            f
            for f in candidates_gefs
            if re.search(r"_\d{2,3}-\d{2,3}(?:_|\.csv$)", os.path.basename(f))
        ]
        if not candidates_gefs:
            raise FileNotFoundError(
                "No GEFS aggregated CSV found in processed directory."
            )
        # Sort by mtime ascending for deterministic order
        gefs_csvs = sorted(candidates_gefs, key=os.path.getmtime)

        # ERA5 daily tp
        candidates_tp = glob.glob(
            os.path.join(self.processed_dir, "era5_tp_daily_*.csv")
        )
        if not candidates_tp:
            raise FileNotFoundError(
                "No ERA5 tp daily CSV found in processed directory."
            )
        era5_tp_csv = max(candidates_tp, key=os.path.getmtime)

        # ERA5 daily t2m
        candidates_t2m = glob.glob(
            os.path.join(self.processed_dir, "era5_t2m_daily_*.csv")
        )
        if not candidates_t2m:
            raise FileNotFoundError(
                "No ERA5 t2m daily CSV found in processed directory."
            )
        era5_t2m_csv = max(candidates_t2m, key=os.path.getmtime)

        return gefs_csvs, era5_tp_csv, era5_t2m_csv

    # ---------- Loaders ----------

    @staticmethod
    def _read_gefs_agg_one(
        gefs_csv: str, logger: logging.Logger
    ) -> pd.DataFrame:
        df = pd.read_csv(gefs_csv)
        required = {
            "forecast_date",
            "member",
            "valid_datetime_start",
            "valid_datetime_range",
            "lead_hours_range",
            "tp",
        }
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(
                f"GEFS CSV missing columns: {sorted(missing)} in {gefs_csv}"
            )
        # Derive start/end datetimes from range if needed
        if "valid_datetime_range" in df.columns:
            if (
                "valid_datetime_end" not in df.columns
                or df["valid_datetime_end"].isna().all()
            ):
                parts = (
                    df["valid_datetime_range"]
                    .astype(str)
                    .str.split(" to ", n=1, expand=True)
                )
                if (
                    "valid_datetime_start" not in df.columns
                    or df["valid_datetime_start"].isna().all()
                ):
                    df["valid_datetime_start"] = parts[0]
                df["valid_datetime_end"] = parts[1]

        # Parse dtypes
        df["forecast_date"] = pd.to_datetime(
            df["forecast_date"].astype(str),
            errors="coerce",
        ).dt.date
        df["valid_datetime_start"] = pd.to_datetime(
            df["valid_datetime_start"], errors="coerce"
        )
        df["valid_datetime_end"] = pd.to_datetime(
            df["valid_datetime_end"], errors="coerce"
        )
        df["tp"] = pd.to_numeric(df["tp"], errors="coerce")
        # Drop rows with bad times
        df = df.dropna(
            subset=["valid_datetime_start", "valid_datetime_end"]
        )  # keep forecast_date even if NaT? but usually ok
        logger.info(
            f"Loaded GEFS aggregated rows: {len(df):,} from {os.path.basename(gefs_csv)}"
        )
        return df

    def _read_gefs_concat(self, gefs_csvs: List[str]) -> pd.DataFrame:
        dfs: List[pd.DataFrame] = [
            self._read_gefs_agg_one(p, self.logger) for p in gefs_csvs
        ]
        if not dfs:
            raise ValueError("No GEFS CSVs provided to concatenate.")
        combined = pd.concat(dfs, ignore_index=True)
        # Deduplicate on (forecast_date, member, valid_datetime_start, lead_hours_range)
        before = len(combined)
        combined = combined.drop_duplicates(
            subset=[
                "forecast_date",
                "member",
                "valid_datetime_start",
                "lead_hours_range",
            ]
        )
        after = len(combined)
        dropped = before - after
        if dropped > 0:
            self.logger.info(
                f"Dropped {dropped} duplicate GEFS rows after concatenation"
            )
        return combined

    @staticmethod
    def _pivot_gefs(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
        index_cols = [
            "forecast_date",
            "valid_datetime_start",
            "valid_datetime_end",
            "lead_hours_range",
        ]
        pivot = df.pivot_table(
            index=index_cols, columns="member", values="tp", aggfunc="first"
        ).reset_index()
        # Prefix member columns to avoid clashes
        new_cols: Dict[str, str] = {}
        for col in pivot.columns:
            if col in index_cols:
                continue
            new_cols[col] = f"gefs_{col}"
        pivot = pivot.rename(columns=new_cols)
        logger.info(
            f"Pivoted GEFS to wide with {len(pivot.columns) - len(index_cols)} member columns"
        )
        return pivot

    @staticmethod
    def _read_era5_tp_daily(
        csv_path: str, logger: logging.Logger
    ) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        required = {"valid_datetime_start", "valid_datetime_end", "tp"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(
                f"ERA5 tp daily CSV missing columns: {sorted(missing)}"
            )
        df["valid_datetime_start"] = pd.to_datetime(
            df["valid_datetime_start"], errors="coerce"
        )
        df["valid_datetime_end"] = pd.to_datetime(
            df["valid_datetime_end"], errors="coerce"
        )
        df["tp"] = pd.to_numeric(df["tp"], errors="coerce")
        logger.info(f"Loaded ERA5 daily tp rows: {len(df):,}")
        return df

    @staticmethod
    def _read_era5_t2m_daily(
        csv_path: str, logger: logging.Logger
    ) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        required = {
            "valid_datetime_start",
            "valid_datetime_end",
            "t2m_min",
            "t2m_mean",
            "t2m_max",
        }
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(
                f"ERA5 t2m daily CSV missing columns: {sorted(missing)}"
            )
        df["valid_datetime_start"] = pd.to_datetime(
            df["valid_datetime_start"], errors="coerce"
        )
        df["valid_datetime_end"] = pd.to_datetime(
            df["valid_datetime_end"], errors="coerce"
        )
        for c in ["t2m_min", "t2m_mean", "t2m_max"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        logger.info(f"Loaded ERA5 daily t2m rows: {len(df):,}")
        return df

    # ---------- Assembly ----------

    def assemble(
        self,
        gefs_csv: Union[str, List[str]],
        era5_tp_daily_csv: str,
        era5_t2m_daily_csv: str,
        output_csv: Optional[str] = None,
    ) -> AssembledDataset:
        """Assemble and write merged dataset.

        Parameters
        ----------
        gefs_csv : str
            Path to GEFS aggregated TP CSV.
        era5_tp_daily_csv : str
            Path to ERA5 daily TP CSV (already in mm).
        era5_t2m_daily_csv : str
            Path to ERA5 daily t2m CSV (min, mean, max).
        output_csv : str, optional
            Where to write the merged dataset. If None, computed from inputs.

        Returns
        -------
        AssembledDataset
            Metadata about the written dataset.
        """
        # Load (support multiple GEFS aggregated files)
        if isinstance(gefs_csv, list):
            gefs_paths = gefs_csv
        else:
            gefs_paths = [gefs_csv]
        gefs_df = self._read_gefs_concat(gefs_paths)
        gefs_wide = self._pivot_gefs(gefs_df, self.logger)

        tp_df = self._read_era5_tp_daily(era5_tp_daily_csv, self.logger)
        t2m_df = self._read_era5_t2m_daily(era5_t2m_daily_csv, self.logger)

        # Merge ERA5 truth for same valid window (start & end)
        merged = gefs_wide.merge(
            tp_df.rename(columns={"tp": "era5_tp"}),
            on=["valid_datetime_start", "valid_datetime_end"],
            how="left",
        )

        # Create lag-1 join keys from forecast_date
        merged["forecast_date"] = pd.to_datetime(
            merged["forecast_date"], errors="coerce"
        )
        merged["lag1_day_start"] = merged["forecast_date"].dt.floor(
            "D"
        ) - pd.Timedelta(days=1)

        # Build lookup series for lag joins keyed by valid_datetime_start
        tp_lag = tp_df.set_index("valid_datetime_start")["tp"].rename(
            "era5_tp_lag1"
        )
        t2m_lag = t2m_df.set_index("valid_datetime_start")[
            ["t2m_min", "t2m_mean", "t2m_max"]
        ].rename(
            columns={
                "t2m_min": "era5_t2m_min_lag1",
                "t2m_mean": "era5_t2m_mean_lag1",
                "t2m_max": "era5_t2m_max_lag1",
            }
        )

        merged = merged.join(tp_lag, on="lag1_day_start")
        merged = merged.join(t2m_lag, on="lag1_day_start")

        # Lag-0 joins aligned to forecast date's day start
        merged["lag0_day_start"] = merged["forecast_date"].dt.floor("D")

        # GEFS geavg whose valid start equals the forecast date (forecast made for that date)
        if "gefs_geavg" in gefs_wide.columns:
            geavg_on_fd = gefs_wide.set_index("valid_datetime_start")[
                "gefs_geavg"
            ].rename("gefs_geavg_on_forecast_date")
            merged = merged.join(geavg_on_fd, on="lag0_day_start")

        # ERA5 tp observation for the forecast date (lag0)
        tp_lag0 = tp_df.set_index("valid_datetime_start")["tp"].rename(
            "era5_tp_lag0"
        )
        merged = merged.join(tp_lag0, on="lag0_day_start")

        # Forecast error on forecast date: GEFS geavg (for that date) minus ERA5 obs for that date
        if (
            "gefs_geavg_on_forecast_date" in merged.columns
            and "era5_tp_lag0" in merged.columns
        ):
            merged["gefs_geavg_on_forecast_date_error"] = (
                merged["gefs_geavg_on_forecast_date"] - merged["era5_tp_lag0"]
            )

        # Error for the same valid window: GEFS mean minus ERA5 truth
        if "gefs_geavg" in merged.columns and "era5_tp" in merged.columns:
            merged["gefs_geavg_error"] = (
                merged["gefs_geavg"] - merged["era5_tp"]
            )

        # Log-transform of lagged ERA5 tp: log(tp + epsilon)
        if "era5_tp_lag1" in merged.columns:
            epsilon_mm: float = 0.1
            merged["era5_tp_lag1_log"] = np.log(
                np.clip(
                    pd.to_numeric(merged["era5_tp_lag1"], errors="coerce"),
                    a_min=0,
                    a_max=None,
                )
                + epsilon_mm
            )

        # Column ordering
        base_cols = [
            "forecast_date",
            "valid_datetime_start",
            "valid_datetime_end",
            "lead_hours_range",
        ]
        # Only include true GEFS member columns in this group; exclude derived extras
        exclude_gefs_derived = {
            "gefs_geavg_on_forecast_date",
            "gefs_geavg_on_forecast_date_error",
            "gefs_geavg_error",
        }
        gefs_cols = [
            c
            for c in merged.columns
            if c.startswith("gefs_") and c not in exclude_gefs_derived
        ]
        extra_cols = [
            "era5_tp",
            "gefs_geavg_error",
            "gefs_geavg_on_forecast_date",
            "era5_tp_lag0",
            "gefs_geavg_on_forecast_date_error",
            "era5_tp_lag1",
            "era5_tp_lag1_log",
            "era5_t2m_min_lag1",
            "era5_t2m_mean_lag1",
            "era5_t2m_max_lag1",
        ]
        ordered_cols = base_cols + sorted(gefs_cols) + extra_cols
        # Deduplicate while preserving order
        ordered_cols = list(dict.fromkeys(ordered_cols))
        # Keep any other passthrough columns at end
        remaining = [c for c in merged.columns if c not in ordered_cols]
        final_df = merged[ordered_cols + remaining].copy()

        # Drop rows without GEFS mean or ERA5 truth
        removed = 0
        for required_col in ["gefs_geavg", "era5_tp"]:
            if required_col not in final_df.columns:
                self.logger.warning(
                    f"Required column missing for filtering: {required_col}"
                )
        have_cols = all(
            c in final_df.columns for c in ["gefs_geavg", "era5_tp"]
        )
        if have_cols:
            before = len(final_df)
            final_df = final_df.dropna(subset=["gefs_geavg", "era5_tp"])
            removed = before - len(final_df)
            if removed > 0:
                self.logger.info(
                    f"Removed {removed} rows with NaN in gefs_geavg or era5_tp"
                )

        # Output path
        if output_csv is None:
            # Derive lead range and grid suffix from the first GEFS file name
            first_gefs_name = os.path.basename(gefs_paths[0])
            lead_range = (
                self._parse_lead_range_from_name(first_gefs_name) or "lead"
            )
            grid_suffix = self._extract_grid_suffix(first_gefs_name)
            start_dt = pd.to_datetime(
                final_df["valid_datetime_start"], errors="coerce"
            ).min()
            end_dt = pd.to_datetime(
                final_df["valid_datetime_end"], errors="coerce"
            ).max()
            date_str = (
                f"{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}"
                if pd.notna(start_dt) and pd.notna(end_dt)
                else "unknown"
            )
            fname_parts: List[str] = ["dataset_gefs_era5", lead_range]
            if grid_suffix:
                fname_parts.insert(1, grid_suffix)
            out_name = "_".join(fname_parts) + f"_{date_str}.csv"
            output_csv = os.path.join(self.processed_dir, out_name)

        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        final_df.to_csv(output_csv, index=False)
        self.logger.info(
            f"Wrote assembled dataset: {output_csv} (rows={len(final_df):,}, gefs_cols={len(gefs_cols)})"
        )

        return AssembledDataset(
            output_path=output_csv,
            num_rows=len(final_df),
            num_gefs_columns=len(gefs_cols),
        )
