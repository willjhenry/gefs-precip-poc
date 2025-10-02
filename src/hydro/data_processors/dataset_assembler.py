from __future__ import annotations

import glob
import logging
import os
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from hydro.common import PROCESSED_DIR


@dataclass
class AssembledDataset:
    """Metadata for the assembled dataset output."""

    output_path: str
    num_rows: int
    num_columns: int


class DatasetAssembler:
    """Build a wide dataset from GEFS aggregated TP and ERA5 daily data.

    - Pivots GEFS members (control, perturbed, mean, spread) to columns
    - Joins ERA5 daily TP as truth on valid day window
    - Adds lag-1 ERA5 TP and t2m (min/mean/max) based on forecast date - 1 day
    - Adds ensemble statistics (min/max/quantiles/skew/kurtosis) for GEFS perturbed members
    - Adds monthly indicator columns (jan-dec) based on valid_datetime_start
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.processed_dir = PROCESSED_DIR

    # ---------- Auto-discovery helpers ----------

    @staticmethod
    def _parse_date_range_from_name(
        filename: str,
    ) -> tuple[str | None, str | None]:
        # Try new format first: YYYYMMDD-YYYYMMDD
        m = re.search(r"_(\d{8})-(\d{8})\.csv$", filename)
        if m:
            return m.group(1), m.group(2)
        # Fallback to old format: YYYYMMDD_YYYYMMDD
        m = re.search(r"_(\d{8})_(\d{8})", filename)
        if m:
            return m.group(1), m.group(2)
        return None, None

    @staticmethod
    def _parse_lead_range_from_name(filename: str) -> str | None:
        # Support new format: ..._lead-120-144_...
        m = re.search(r"lead-(\d{2,3}-\d{2,3})", filename)
        if m:
            return m.group(1)
        # Fallback to old format: ..._120-144.csv or ..._120-144_YYYYMMDD_YYYYMMDD.csv
        m = re.search(r"_(\d{2,3}-\d{2,3})(?:_|\.csv$)", filename)
        return m.group(1) if m else None

    @staticmethod
    def _extract_grid_suffix(filename: str) -> str:
        # Try new format first: lat-47p5_lon-8p0
        m = re.search(r"lat-([0-9p-]+)_lon-([0-9p-]+)", filename)
        if m:
            lat_str, lon_str = m.groups()
            lat = float(lat_str.replace("p", "."))
            lon = float(lon_str.replace("p", "."))
            return f"({lat},{lon})"
        # Fallback to old format: (-47p5,-8p0)
        m = re.search(r"(\(-?\d+p\d,\-?\d+p\d\))", filename)
        return m.group(1) if m else ""

    def find_inputs(self) -> tuple[list[str], str, str]:
        """Locate processed files for GEFS aggregated and ERA5 daily.

        Returns
        -------
        tuple
            (list_of_gefs_csvs, era5_tp_daily_csv, era5_t2m_daily_csv)
        """
        # GEFS aggregated (new structured paths first, then fallback)
        candidates_gefs_new = glob.glob(
            os.path.join(
                self.processed_dir, "gefs", "**", "gefs_tp_sum_*.csv"
            ),
            recursive=True,
        )
        if not candidates_gefs_new:
            # Fallback to old paths
            candidates_gefs_new = glob.glob(
                os.path.join(self.processed_dir, "gefs_ensemble_tp*.csv")
            )
            candidates_gefs_new = [
                f
                for f in candidates_gefs_new
                if re.search(
                    r"_\d{2,3}-\d{2,3}(?:_|\.csv$)", os.path.basename(f)
                )
            ]
        if not candidates_gefs_new:
            raise FileNotFoundError(
                "No GEFS aggregated CSV found in processed directory."
            )
        # Sort by mtime ascending for deterministic order
        gefs_csvs = sorted(candidates_gefs_new, key=os.path.getmtime)

        # ERA5 daily tp (new structured paths first, then fallback)
        candidates_tp_new = glob.glob(
            os.path.join(
                self.processed_dir, "era5", "**", "era5_tp_freq-1d_*.csv"
            ),
            recursive=True,
        )
        if not candidates_tp_new:
            # Fallback to old paths
            candidates_tp_new = glob.glob(
                os.path.join(self.processed_dir, "era5_tp_daily_*.csv")
            )
        if not candidates_tp_new:
            raise FileNotFoundError(
                "No ERA5 tp daily CSV found in processed directory."
            )
        era5_tp_csv = max(candidates_tp_new, key=os.path.getmtime)

        # ERA5 daily t2m (new structured paths first, then fallback)
        candidates_t2m_new = glob.glob(
            os.path.join(
                self.processed_dir, "era5", "**", "era5_t2m_freq-1d_*.csv"
            ),
            recursive=True,
        )
        if not candidates_t2m_new:
            # Fallback to old paths
            candidates_t2m_new = glob.glob(
                os.path.join(self.processed_dir, "era5_t2m_daily_*.csv")
            )
        if not candidates_t2m_new:
            raise FileNotFoundError(
                "No ERA5 t2m daily CSV found in processed directory."
            )
        era5_t2m_csv = max(candidates_t2m_new, key=os.path.getmtime)

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

    def _read_gefs_concat(self, gefs_csvs: list[str]) -> pd.DataFrame:
        dfs: list[pd.DataFrame] = [
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
        new_cols: dict[str, str] = {}
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
        gefs_csv: str | list[str],
        era5_tp_daily_csv: str,
        era5_t2m_daily_csv: str,
        output_csv: str | None = None,
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
        # GEFS
        gefs_paths = self._get_gefs_paths(gefs_csv)
        gefs_wide = self._process_gefs_columns(gefs_paths)

        # ERA5
        merged = self._merge_in_era5_features(
            gefs_wide, era5_tp_daily_csv, era5_t2m_daily_csv
        )

        # Monthly indicator columns
        merged = self._add_monthly_indicator_columns(merged)

        # Add a bias column (column of ones) - is this needed for tensor flow?
        merged["bias"] = 1

        # Filter rows
        merged = self._filter_rows(merged)

        # Order columns
        final_df = self._order_columns(merged)

        # Output path
        if output_csv is None:
            output_csv = self._get_output_path(gefs_paths[0], final_df)

        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        final_df.to_csv(output_csv, index=False)
        self.logger.info(
            f"Wrote assembled dataset: {output_csv} (rows={len(final_df):,}, cols={len(final_df.columns)})"
        )

        return AssembledDataset(
            output_path=output_csv,
            num_rows=len(final_df),
            num_columns=len(final_df.columns),
        )

    def _get_output_path(
        self, gefs_path: str, final_df: pd.DataFrame
    ) -> str:  # Derive lead range and grid info from the first GEFS file name
        first_gefs_name = os.path.basename(gefs_path)
        lead_range = (
            self._parse_lead_range_from_name(first_gefs_name) or "lead"
        )
        grid_suffix = self._extract_grid_suffix(first_gefs_name)
        # For new format, convert grid_suffix to new style if it's the old format
        if grid_suffix.startswith("(") and grid_suffix.endswith(")"):
            # Old format: (47.5,8.0) -> lat-47p5_lon-8p0
            parts = grid_suffix.strip("()").split(",")
            if len(parts) == 2:
                lat_str = parts[0].strip()
                lon_str = parts[1].strip()
                grid_suffix = f"lat-{lat_str.replace('.', 'p')}_lon-{lon_str.replace('.', 'p')}"
        start_dt = final_df["valid_datetime_start"].min()
        end_dt = final_df["valid_datetime_end"].max()
        date_str = (
            f"{start_dt.strftime('%Y%m%d')}-{end_dt.strftime('%Y%m%d')}"
            if pd.notna(start_dt) and pd.notna(end_dt)
            else "unknown-unknown"
        )
        fname_parts: list[str] = ["dataset_gefs_era5"]
        if grid_suffix:
            fname_parts.append(grid_suffix)
        fname_parts.append(f"lead-{lead_range}")
        out_name = "_".join(fname_parts) + f"_{date_str}.csv"
        # Place under data/processed/datasets/<grid>/lead_<range>/
        base_dir = os.path.join(self.processed_dir, "datasets")
        out_dir = base_dir
        if grid_suffix:
            out_dir = os.path.join(out_dir, grid_suffix)
        # Use underscore for directory, hyphen remains in filename tag
        out_dir = os.path.join(out_dir, f"lead_{lead_range}")
        os.makedirs(out_dir, exist_ok=True)
        output_csv = os.path.join(out_dir, out_name)
        return output_csv

    def _get_gefs_paths(self, gefs_csv: str | list[str]) -> list[str]:
        # Load (support multiple GEFS aggregated files)
        if isinstance(gefs_csv, list):
            gefs_paths = gefs_csv
        else:
            gefs_paths = [gefs_csv]
        return gefs_paths

    def _process_gefs_columns(self, gefs_paths: list[str]) -> pd.DataFrame:
        gefs_df = self._read_gefs_concat(gefs_paths)
        gefs_wide = self._pivot_gefs(gefs_df, self.logger)

        # Add min/max columns for GEFS ensemble members (perturbed members only)
        gefs_member_cols = [
            col for col in gefs_wide.columns if col.startswith("gefs_gep")
        ]
        if gefs_member_cols:
            gefs_wide["gefs_ensemble_min"] = gefs_wide[gefs_member_cols].min(
                axis=1
            )
            gefs_wide["gefs_ensemble_max"] = gefs_wide[gefs_member_cols].max(
                axis=1
            )
            gefs_wide["gefs_ensemble_q10"] = gefs_wide[
                gefs_member_cols
            ].quantile(0.1, axis=1)
            gefs_wide["gefs_ensemble_q90"] = gefs_wide[
                gefs_member_cols
            ].quantile(0.9, axis=1)
            gefs_wide["gefs_ensemble_skew"] = gefs_wide[gefs_member_cols].skew(
                axis=1
            )
            gefs_wide["gefs_ensemble_kurtosis"] = gefs_wide[
                gefs_member_cols
            ].kurt(axis=1)
        return gefs_wide

    def _merge_in_era5_features(
        self,
        merged: pd.DataFrame,
        era5_tp_daily_csv: str,
        era5_t2m_daily_csv: str,
    ) -> pd.DataFrame:
        tp_df = self._read_era5_tp_daily(era5_tp_daily_csv, self.logger)
        t2m_df = self._read_era5_t2m_daily(era5_t2m_daily_csv, self.logger)

        # Merge ERA5 truth for same valid window (start & end)
        merged = merged.merge(
            tp_df.rename(columns={"tp": "era5_tp"}),
            on=["valid_datetime_start", "valid_datetime_end"],
            how="left",
        )
        # Lag features

        merged["lag1_day_start"] = pd.to_datetime(
            merged["forecast_date"], errors="coerce"
        ).dt.floor("D") - pd.Timedelta(days=1)

        # Build lookup series for lag joins keyed by valid_datetime_start
        tp_lag = tp_df.set_index("valid_datetime_start")["tp"].rename(
            "era5_tp_lag1"
        )

        # Log transform
        epsilon_mm: float = 0.1
        tp_lag_log = np.log(
            np.clip(
                pd.to_numeric(tp_lag, errors="coerce"),
                a_min=0,
                a_max=None,
            )
            + epsilon_mm
        )
        # convert to frame
        tp_lag = tp_lag.to_frame()
        tp_lag["era5_tp_lag1_log"] = tp_lag_log

        # convert index to datetime
        tp_lag.index = pd.to_datetime(tp_lag.index, errors="coerce")

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

        # we can now drop "lag1_day_start" column
        merged = merged.drop(columns=["lag1_day_start"])

        return merged

    def _add_monthly_indicator_columns(
        self, merged: pd.DataFrame
    ) -> (
        pd.DataFrame
    ):  # Add monthly indicator columns based on valid_datetime_start
        if "valid_datetime_start" in merged.columns:
            month_names = [
                "jan",
                "feb",
                "mar",
                "apr",
                "may",
                "jun",
                "jul",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
            ]
            for i, month_name in enumerate(month_names, 1):
                merged[month_name] = (
                    merged["valid_datetime_start"].dt.month == i
                ).astype(int)
        return merged

    def _filter_rows(
        self, merged: pd.DataFrame
    ) -> pd.DataFrame:  # Drop rows without GEFS mean or ERA5 truth
        for required_col in ["gefs_geavg", "era5_tp"]:
            if required_col not in merged.columns:
                self.logger.warning(
                    f"Required column missing for filtering: {required_col}"
                )
        have_cols = all(c in merged.columns for c in ["gefs_geavg", "era5_tp"])
        if have_cols:
            before = len(merged)
            merged = merged.dropna(subset=["gefs_geavg", "era5_tp"])
            removed = before - len(merged)
            if removed > 0:
                self.logger.info(
                    f"Removed {removed} rows with NaN in gefs_geavg or era5_tp"
                )
        return merged

    def _order_columns(
        self, merged: pd.DataFrame
    ) -> pd.DataFrame:  # Column ordering
        base_cols = [
            "forecast_date",
            "valid_datetime_start",
            "valid_datetime_end",
            "lead_hours_range",
        ]
        extra_cols = [
            "era5_tp",
            "era5_tp_lag1",
            "era5_tp_lag1_log",
            "era5_t2m_min_lag1",
            "era5_t2m_mean_lag1",
            "era5_t2m_max_lag1",
            "gefs_ensemble_min",
            "gefs_ensemble_max",
            "gefs_ensemble_q10",
            "gefs_ensemble_q90",
            "gefs_ensemble_skew",
            "gefs_ensemble_kurtosis",
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ]
        gefs_cols = [
            c
            for c in merged.columns
            if c.startswith("gefs_") and c not in extra_cols
        ]
        ordered_cols = base_cols + sorted(gefs_cols) + extra_cols
        # Deduplicate while preserving order
        ordered_cols = list(dict.fromkeys(ordered_cols))
        # Keep any other passthrough columns at end
        remaining = [c for c in merged.columns if c not in ordered_cols]

        return merged.loc[:, ordered_cols + remaining]
