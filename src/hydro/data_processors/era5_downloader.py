"""
ERA5 downloader utilities.

Implements `Era5Downloader` for fetching ERA5 reanalysis data using the
Copernicus CDS API for a single latitude/longitude point.
"""

from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from typing import Optional, Tuple

import cdsapi

from hydro.common import RAW_ERA5_DIR, grid_tags


class Era5Downloader:
    """Download ERA5 reanalysis data for a fixed point location.

    Parameters
    ----------
    location
        Tuple of (latitude, longitude) in decimal degrees.
    logger
        Optional logger. If not provided, a module-level logger is used.
    dataset
        CDS dataset identifier. Defaults to
        "reanalysis-era5-single-levels-timeseries".

    Notes
    -----
    - Requires `cdsapi` and configured CDS API credentials.
    - Only supports single point retrieval with NetCDF output.
    """

    VARIABLE_MAP = {"tp": "total_precipitation", "t2m": "2m_temperature"}

    def __init__(
        self,
        location: Tuple[float, float],
        logger: Optional[logging.Logger] = None,
        dataset: str = "reanalysis-era5-single-levels-timeseries",
    ) -> None:
        self.location = location
        self.output_root = RAW_ERA5_DIR
        self.dataset = dataset
        self.logger = logger or logging.getLogger(__name__)

    def build_output_path(
        self, variable: str, start_date: str, end_date: str
    ) -> str:
        """Construct the initial download target path for a request.

        Parameters
        ----------
        variable
            Short variable key (e.g., "tp" or "t2m").
        start_date
            Start date in YYYY-MM-DD format.
        end_date
            End date in YYYY-MM-DD format.

        Returns
        -------
        str
            Absolute path to the initial download target (ZIP by default; may be
            a direct NetCDF depending on CDS response). Post-download logic will
            convert `.zip` to `.nc` if needed.
        """
        safe_start = start_date.replace("-", "")
        safe_end = end_date.replace("-", "")
        lat, lon = self.location
        grid = grid_tags(lat, lon)
        out_dir = os.path.join(self.output_root, grid, variable)
        os.makedirs(out_dir, exist_ok=True)

        # Standardized raw filename base (we target .zip for the initial download)
        filename_zip = f"era5_{variable}_{grid}_{safe_start}-{safe_end}.zip"
        return os.path.join(out_dir, filename_zip)

    @staticmethod
    def build_date_range(start_date: str, end_date: str) -> str:
        """Build a CDS API date range string.

        Parameters
        ----------
        start_date
            Start date in YYYY-MM-DD format.
        end_date
            End date in YYYY-MM-DD format.

        Returns
        -------
        str
            Date range string in the form "YYYY-MM-DD/YYYY-MM-DD".
        """
        return f"{start_date}/{end_date}"

    def download(self, variable: str, start_date: str, end_date: str) -> str:
        """Download ERA5 data for the given variable and date range.

        Parameters
        ----------
        variable
            Short variable key: "tp" (total_precipitation) or "t2m" (2m_temperature).
        start_date
            Start date in YYYY-MM-DD format.
        end_date
            End date in YYYY-MM-DD format.

        Returns
        -------
        str
            Path to the downloaded NetCDF file.

        Raises
        ------
        ValueError
            If `variable` is not supported.
        Exception
            Propagates any errors from the CDS API client.
        """
        if variable not in self.VARIABLE_MAP:
            raise ValueError(
                f"Unknown variable: {variable}. Use one of {list(self.VARIABLE_MAP.keys())}"
            )

        cds_variable = self.VARIABLE_MAP[variable]
        date_range = self.build_date_range(start_date, end_date)

        # Ensure root exists (subdirs ensured in build_output_path)
        os.makedirs(self.output_root, exist_ok=True)
        output_zip_or_nc = self.build_output_path(
            variable, start_date, end_date
        )

        self.logger.info(
            f"Downloading ERA5 {variable} ({cds_variable}) for {date_range}"
        )
        self.logger.info(f"Location: {self.location}")
        self.logger.info(f"Output (initial): {output_zip_or_nc}")

        request = {
            "variable": [cds_variable],
            "location": {
                "longitude": self.location[1],
                "latitude": self.location[0],
            },
            "date": [date_range],
            "data_format": "netcdf",
        }

        try:
            client = cdsapi.Client()
            client.retrieve(self.dataset, request, target=output_zip_or_nc)
            self.logger.info(
                f"Successfully downloaded ERA5 data to {output_zip_or_nc}"
            )

            # Handle potential ZIP compression from CDS API

            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    with zipfile.ZipFile(output_zip_or_nc, "r") as zip_ref:
                        zip_ref.extractall(temp_dir)
                        inner_files = [
                            f
                            for f in os.listdir(temp_dir)
                            if f.endswith(".nc")
                        ]
                        if len(inner_files) == 1:
                            inner_nc = os.path.join(temp_dir, inner_files[0])
                            final_nc = output_zip_or_nc.replace(".zip", ".nc")
                            os.rename(inner_nc, final_nc)
                            os.remove(output_zip_or_nc)
                            self.logger.info(
                                f"Extracted ZIP and moved inner NetCDF to {final_nc}"
                            )
                            output_path = final_nc
                        else:
                            self.logger.warning(
                                f"ZIP contained {len(inner_files)} .nc files; not extracting automatically."
                            )
                            output_path = output_zip_or_nc
                except zipfile.BadZipFile:
                    # Not a ZIP; it's already the NetCDF
                    final_nc = output_zip_or_nc.replace(".zip", ".nc")
                    try:
                        os.rename(output_zip_or_nc, final_nc)
                        self.logger.info(
                            f"Downloaded file is NetCDF; renamed to {final_nc}"
                        )
                        output_path = final_nc
                    except Exception:
                        # If rename fails, fall back to returning original path
                        self.logger.warning(
                            f"Could not rename {output_zip_or_nc} to .nc; using original path"
                        )
                        output_path = output_zip_or_nc

            # Return resolved output path
            return output_path
        except Exception:
            self.logger.exception("Failed to download ERA5 data")
            raise
