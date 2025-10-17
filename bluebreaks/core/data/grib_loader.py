"""
GRIB data loader for WaveWatch III and GFS forecasts

Loads and processes GRIB files containing:
- Wave data: significant wave height (Hs), period (Tp), direction (Dp)
- Wind data: U/V components, speed, direction
"""

import xarray as xr
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GRIBLoader:
    """Load and process GRIB wave and wind forecast data"""

    def __init__(self, grib_path: Path):
        """
        Initialize GRIB loader

        Args:
            grib_path: Path to GRIB file (*.grb, *.grb2)
        """
        self.grib_path = Path(grib_path)
        if not self.grib_path.exists():
            raise FileNotFoundError(f"GRIB file not found: {grib_path}")

        self.ds: Optional[xr.Dataset] = None

    def load(self) -> xr.Dataset:
        """
        Load GRIB file using cfgrib backend

        Returns:
            xarray Dataset with wave/wind variables
        """
        try:
            # Try loading with cfgrib (supports GRIB1 and GRIB2)
            self.ds = xr.open_dataset(
                self.grib_path,
                engine="cfgrib",
                backend_kwargs={
                    "indexpath": "",  # Don't create index files
                    "errors": "ignore",  # Skip problematic messages
                },
            )
            logger.info(f"Loaded GRIB: {self.grib_path} with {len(self.ds.data_vars)} variables")
            return self.ds

        except Exception as e:
            logger.error(f"Failed to load GRIB file: {e}")
            raise

    def extract_wave_data(
        self,
        lon_range: Optional[Tuple[float, float]] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        time: Optional[datetime] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Extract wave parameters (Hs, Tp, Dp) for a region/time

        Args:
            lon_range: (min_lon, max_lon) or None for all
            lat_range: (min_lat, max_lat) or None for all
            time: Specific datetime or None for first timestep

        Returns:
            Dictionary with 'hs', 'tp', 'dp', 'lon', 'lat', 'time'
        """
        if self.ds is None:
            self.load()

        ds = self.ds

        # Subset by region
        if lon_range:
            ds = ds.sel(longitude=slice(lon_range[0], lon_range[1]))
        if lat_range:
            ds = ds.sel(latitude=slice(lat_range[0], lat_range[1]))

        # Subset by time
        if time:
            ds = ds.sel(time=time, method="nearest")
        else:
            ds = ds.isel(time=0)

        # Extract wave variables (try common WW3 naming conventions)
        wave_data = {}

        # Significant wave height (m)
        for hs_var in ["swh", "hs", "htsgw", "HTSGW"]:
            if hs_var in ds:
                wave_data["hs"] = ds[hs_var].values
                break

        # Peak period (s)
        for tp_var in ["pp1d", "tp", "perpw", "PERPW"]:
            if tp_var in ds:
                wave_data["tp"] = ds[tp_var].values
                break

        # Wave direction (degrees, meteorological convention)
        for dp_var in ["dirpw", "dp", "wvdir", "WVDIR"]:
            if dp_var in ds:
                wave_data["dp"] = ds[dp_var].values
                break

        # Coordinates
        wave_data["lon"] = ds.longitude.values
        wave_data["lat"] = ds.latitude.values
        wave_data["time"] = ds.time.values if "time" in ds.dims else None

        # Validate we got the essentials
        if "hs" not in wave_data or "tp" not in wave_data or "dp" not in wave_data:
            available = list(ds.data_vars.keys())
            logger.warning(
                f"Missing wave variables. Available: {available}. "
                f"Got: {list(wave_data.keys())}"
            )

        return wave_data

    def extract_wind_data(
        self,
        lon_range: Optional[Tuple[float, float]] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        time: Optional[datetime] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Extract wind parameters (U, V components, speed, direction)

        Args:
            lon_range: (min_lon, max_lon) or None for all
            lat_range: (min_lat, max_lat) or None for all
            time: Specific datetime or None for first timestep

        Returns:
            Dictionary with 'u', 'v', 'speed', 'direction', 'lon', 'lat', 'time'
        """
        if self.ds is None:
            self.load()

        ds = self.ds

        # Subset by region
        if lon_range:
            ds = ds.sel(longitude=slice(lon_range[0], lon_range[1]))
        if lat_range:
            ds = ds.sel(latitude=slice(lat_range[0], lat_range[1]))

        # Subset by time
        if time:
            ds = ds.sel(time=time, method="nearest")
        else:
            ds = ds.isel(time=0)

        wind_data = {}

        # U/V wind components (m/s)
        for u_var in ["u10", "u", "ugrd", "UGRD"]:
            if u_var in ds:
                wind_data["u"] = ds[u_var].values
                break

        for v_var in ["v10", "v", "vgrd", "VGRD"]:
            if v_var in ds:
                wind_data["v"] = ds[v_var].values
                break

        # Calculate speed and direction if we have U/V
        if "u" in wind_data and "v" in wind_data:
            u = wind_data["u"]
            v = wind_data["v"]

            # Wind speed (m/s)
            wind_data["speed"] = np.sqrt(u**2 + v**2)

            # Wind direction (degrees, meteorological convention: direction FROM)
            wind_data["direction"] = (np.degrees(np.arctan2(-u, -v)) + 360) % 360

        # Coordinates
        wind_data["lon"] = ds.longitude.values
        wind_data["lat"] = ds.latitude.values
        wind_data["time"] = ds.time.values if "time" in ds.dims else None

        return wind_data

    def get_time_range(self) -> Tuple[datetime, datetime]:
        """Get forecast time range"""
        if self.ds is None:
            self.load()

        times = self.ds.time.values
        return times[0], times[-1]

    def get_available_times(self) -> np.ndarray:
        """Get all available forecast times"""
        if self.ds is None:
            self.load()

        return self.ds.time.values

    def close(self) -> None:
        """Close the dataset"""
        if self.ds is not None:
            self.ds.close()
            self.ds = None

    def __enter__(self) -> "GRIBLoader":
        """Context manager entry"""
        self.load()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit"""
        self.close()


def load_ww3_forecast(
    grib_path: Path,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Convenience function to load WW3 forecast data

    Args:
        grib_path: Path to GRIB file
        bbox: (min_lon, min_lat, max_lon, max_lat) or None
        time: Specific datetime or None for first timestep

    Returns:
        Dictionary with 'wave' and 'wind' data
    """
    lon_range = (bbox[0], bbox[2]) if bbox else None
    lat_range = (bbox[1], bbox[3]) if bbox else None

    with GRIBLoader(grib_path) as loader:
        wave_data = loader.extract_wave_data(lon_range, lat_range, time)
        wind_data = loader.extract_wind_data(lon_range, lat_range, time)

    return {"wave": wave_data, "wind": wind_data}
