"""
NetCDFDataExtractor: Extract time series from ERA5 NetCDF files at a specific lat/lon grid point.

Uses xarray for efficient, coordinate-aware selection.
"""

from __future__ import annotations

import importlib.util
import logging
import os

import pandas as pd
import xarray as xr

from hydro.common import build_era5_basename, grid_point_string

logger = logging.getLogger(__name__)


class NetCDFDataExtractor:
    """Class to extract time series data from NetCDF files (e.g., ERA5) at a grid point.

    Uses xarray with the "h5netcdf" backend by default to open NetCDF files.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        variable: str = "tp",  # e.g., "tp" for total precipitation, "t2m" for 2m temperature
        method: str = "nearest",  # xarray sel method: "nearest"
        engine: str = "netcdf4",  # xarray backend engine for NetCDF
    ) -> None:
        """
        Initialize the extractor.

        Parameters
        ----------
        lat : float
            Latitude of the grid point (e.g., 47.5 for Rhine).
        lon : float
            Longitude of the grid point (e.g., 8.0 for Rhine).
        variable : str
            NetCDF variable to extract (e.g., "tp", "t2m").
        method : str
            Interpolation method for lat/lon selection ("nearest" or "bilinear").

        """
        self.lat = lat
        self.lon = lon
        self.variable = variable
        self.method = method
        self.grid_str = grid_point_string(lat, lon)
        self.engine = engine
        self.logger = logger or logging.getLogger(__name__)

    def extract_to_dataframe(self, file_path: str) -> pd.DataFrame:
        """Extract time series data for a specific lat/lon point from a NetCDF file.

        Parameters
        ----------
        file_path : str
            Path to the NetCDF file.

        Returns
        -------
        pd.DataFrame
            DataFrame with 'valid_time' (YYYY-MM-DD HH:MM:SS) and 'value' columns.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the variable is not found or coordinates cannot be resolved.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"NetCDF file not found: {file_path}")

        self.logger.info(
            f"Extracting {self.variable} from {file_path} at ({self.lat}, {self.lon})"
        )

        # Open with xarray (lazy loading) using robust backend selection
        ds, opened_with = self._open_dataset_with_fallback(
            file_path, self.engine
        )
        self.logger.debug(f"Opened with engine: {opened_with}")

        try:
            # Resolve coordinate names
            lat_name, lon_name = self._resolve_coord_names(ds)

            # Check if coords are scalar (single-point) or arrays (gridded)
            is_single_point = (
                lat_name in ds.coords
                and lon_name in ds.coords
                and ds[lat_name].size == 1
                and ds[lon_name].size == 1
            )

            if is_single_point:
                self.logger.info(
                    "Detected single-point dataset; skipping spatial selection."
                )
                if self.variable not in ds:
                    raise ValueError(
                        f"Variable '{self.variable}' not found in dataset."
                    )
                point_data = ds[self.variable]
            else:
                # Gridded data: select nearest point
                self.logger.info(
                    f"Selecting nearest point using {lat_name}/{lon_name}."
                )
                if lat_name not in ds.coords or lon_name not in ds.coords:
                    raise ValueError(
                        f"Could not find spatial coordinates {lat_name}/{lon_name} in dataset."
                    )
                point_data = ds[self.variable].sel(
                    {lat_name: self.lat, lon_name: self.lon},
                    method=self.method,
                )
            # Convert to DataFrame
            df_full = point_data.to_dataframe().reset_index()

            # Standardize column names (handle time as 'time' or similar)
            time_col = next(
                (
                    col
                    for col in df_full.columns
                    if col in ["time", "valid_time", "date"]
                ),
                None,
            )
            if time_col is None:
                raise ValueError("No time coordinate found in dataset.")
            columns_dict = {time_col: "valid_time", self.variable: "value"}
            df = df_full.rename(columns=columns_dict)

            # Convert tp from meters to millimeters to match GEFS units (mm)
            if self.variable == "tp":
                df["value"] = (
                    pd.to_numeric(df["value"], errors="coerce") * 1000.0  # type: ignore
                )

            self.logger.info(
                f"Extracted {len(df)} time steps for {self.variable}."
            )

            return df

        finally:
            ds.close()

    def extract_to_csv(
        self,
        file_path: str,
        output_dir: str,
        prefix: str | None = None,
    ) -> str:
        """
        Extract to DataFrame and save as CSV.

        Parameters
        ----------
        file_path : str
            Input NetCDF path.
        output_dir : str
            Directory to save CSV.
        prefix : str, optional
            Optional prefix for filename (e.g., "era5_").

        Returns
        -------
        str
            Path to the output CSV.

        """
        df = self.extract_to_dataframe(file_path)

        # Infer date range from data (valid_time min/max)
        date_range = self._infer_date_range(file_path, df)

        # Validate variable
        if self.variable not in ["tp", "t2m"]:
            raise ValueError(
                f"Unsupported variable: {self.variable}. Only 'tp' and 't2m' are supported."
            )

        # Use standardized basename
        base = build_era5_basename(
            variable=self.variable,
            frequency="hourly",
            location=(self.lat, self.lon),
        )
        output_filename = f"{base}_{date_range}.csv"
        output_path = os.path.join(output_dir, output_filename)

        # Ensure dir exists
        os.makedirs(output_dir, exist_ok=True)

        # Save
        df.to_csv(output_path, index=False)
        self.logger.info(f"Saved CSV to {output_path}")
        return output_path

    @staticmethod
    def _infer_date_range(file_path: str, df: pd.DataFrame) -> str:
        """Infer YYYYMMDD_YYYYMMDD from filename or data."""
        # Fallback to data min/max (prioritize valid_time)
        if not df.empty and "valid_time" in df.columns:
            start = df["valid_time"].min()
            end = df["valid_time"].max()
            return f"{pd.to_datetime(start).strftime('%Y%m%d')}_{pd.to_datetime(end).strftime('%Y%m%d')}"

        # Try to parse from filename (e.g., era5_tp_20230101_20231201.nc)
        base = os.path.basename(file_path)
        if "_20" in base and "_" in base.split("_20")[-1]:
            dates = base.split("_")[-2:]  # Last two parts
            if len(dates) == 2 and all(len(d) == 8 for d in dates):
                return f"{dates[0]}_{dates[1]}"

        return "unknown-unknown"

    @staticmethod
    def _resolve_coord_names(ds: xr.Dataset) -> tuple[str, str]:
        """Resolve latitude/longitude coordinate names across datasets.

        Tries common variants: ("latitude","longitude"), ("lat","lon"), ("y","x").
        """
        candidates = [
            ("latitude", "longitude"),
            ("lat", "lon"),
            ("y", "x"),
        ]
        for lat_name, lon_name in candidates:
            if lat_name in ds.coords and lon_name in ds.coords:
                return lat_name, lon_name
        # Fallback: search dims/coords heuristically
        coord_names = [str(n) for n in list(ds.coords) + list(ds.dims)]
        lat_name = next(
            (n for n in coord_names if n.lower() in ("lat", "latitude")),
            "latitude",
        )
        lon_name = next(
            (n for n in coord_names if n.lower() in ("lon", "longitude")),
            "longitude",
        )
        return str(lat_name), str(lon_name)

    @staticmethod
    def _open_dataset_with_fallback(
        file_path: str, preferred_engine: str
    ) -> tuple[xr.Dataset, str]:
        """Try multiple engines to open a NetCDF/GRIB-like file gracefully.

        Order attempted:
        1) preferred_engine
        2) h5netcdf
        3) netcdf4 (if installed)
        4) scipy
        5) auto (let xarray choose)
        """
        engines = []
        if preferred_engine:
            engines.append(preferred_engine)
        engines.extend(["h5netcdf", "netcdf4", "scipy"])

        last_err: Exception | None = None
        for eng in engines:
            try:
                if (
                    eng == "netcdf4"
                    and importlib.util.find_spec("netCDF4") is None
                ):
                    continue
                ds = xr.open_dataset(file_path, engine=eng)
                return ds, eng
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue

        # Final fallback: auto
        try:
            ds = xr.open_dataset(file_path)
            return ds, "auto"
        except Exception as e:  # noqa: BLE001
            raise e if last_err is None else last_err
