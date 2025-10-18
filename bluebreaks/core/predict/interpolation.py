"""
Spatiotemporal interpolation for buoy observations

Interpolates buoy observations (Hs, Tp, Dp, wind) to arbitrary locations
and times using Inverse Distance Weighting (IDW) and temporal weighting.

Can be extended to kriging later for better spatial correlation modeling.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points on Earth

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth radius in km

    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    dlat = np.radians(lat2 - lat1)

    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


class IDWInterpolator:
    """
    Inverse Distance Weighting interpolator for spatiotemporal buoy data

    Interpolates observations from multiple buoy stations to arbitrary
    locations and times using distance-weighted averaging.
    """

    def __init__(
        self,
        power: float = 2.0,
        max_distance_km: float = 500.0,
        max_time_hours: float = 6.0,
        min_stations: int = 1
    ):
        """
        Initialize IDW interpolator

        Args:
            power: IDW power parameter (higher = more weight to nearby points)
            max_distance_km: Maximum spatial distance to consider stations (km)
            max_time_hours: Maximum temporal distance to consider observations (hours)
            min_stations: Minimum number of stations required for interpolation
        """
        self.power = power
        self.max_distance_km = max_distance_km
        self.max_time_hours = max_time_hours
        self.min_stations = min_stations

    def interpolate_point(
        self,
        target_lat: float,
        target_lon: float,
        target_time: datetime,
        observations: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Interpolate wave parameters to a single point in space and time

        Args:
            target_lat: Target latitude
            target_lon: Target longitude
            target_time: Target datetime
            observations: DataFrame with columns: lat, lon, time, hs, tp, dp, wind_speed, wind_dir

        Returns:
            Dictionary with interpolated values: {hs, tp, dp, wind_speed, wind_dir, n_stations}
        """
        if len(observations) == 0:
            logger.warning("No observations available for interpolation")
            return self._empty_result()

        # Calculate spatial distances
        observations = observations.copy()
        observations['distance_km'] = observations.apply(
            lambda row: haversine_distance(target_lat, target_lon, row['lat'], row['lon']),
            axis=1
        )

        # Calculate temporal distances (hours)
        observations['time_diff_hours'] = observations['time'].apply(
            lambda t: abs((target_time - t).total_seconds() / 3600.0)
        )

        # Filter by max distance and time
        valid_obs = observations[
            (observations['distance_km'] <= self.max_distance_km) &
            (observations['time_diff_hours'] <= self.max_time_hours)
        ]

        if len(valid_obs) < self.min_stations:
            logger.debug(
                f"Insufficient stations ({len(valid_obs)}) for interpolation at "
                f"({target_lat:.2f}, {target_lon:.2f})"
            )
            return self._empty_result()

        # Calculate spatial weights (IDW)
        valid_obs['spatial_weight'] = 1.0 / (valid_obs['distance_km'] ** self.power + 1e-6)

        # Calculate temporal weights (exponential decay)
        # Weight = exp(-time_diff / decay_constant)
        decay_constant = self.max_time_hours / 3.0
        valid_obs['temporal_weight'] = np.exp(-valid_obs['time_diff_hours'] / decay_constant)

        # Combined weight
        valid_obs['weight'] = valid_obs['spatial_weight'] * valid_obs['temporal_weight']

        # Normalize weights
        total_weight = valid_obs['weight'].sum()
        valid_obs['weight'] /= total_weight

        # Interpolate each parameter
        result = {}

        for param in ['hs', 'tp', 'dp', 'wind_speed', 'wind_dir']:
            if param not in valid_obs.columns:
                result[param] = np.nan
                continue

            # Handle circular parameters (directions)
            if param in ['dp', 'wind_dir']:
                result[param] = self._interpolate_circular(valid_obs, param)
            else:
                # Linear weighted average
                valid_data = valid_obs[valid_obs[param].notna()]
                if len(valid_data) > 0:
                    result[param] = (valid_data[param] * valid_data['weight']).sum() / valid_data['weight'].sum()
                else:
                    result[param] = np.nan

        # Add metadata
        result['n_stations'] = len(valid_obs['station_id'].unique())
        result['avg_distance_km'] = (valid_obs['distance_km'] * valid_obs['weight']).sum()
        result['avg_time_diff_hours'] = (valid_obs['time_diff_hours'] * valid_obs['weight']).sum()

        return result

    def _interpolate_circular(self, df: pd.DataFrame, param: str) -> float:
        """
        Interpolate circular parameter (direction) using weighted circular mean

        Args:
            df: DataFrame with 'weight' and param columns
            param: Parameter name (e.g., 'dp', 'wind_dir')

        Returns:
            Interpolated direction (degrees)
        """
        valid_data = df[df[param].notna()]
        if len(valid_data) == 0:
            return np.nan

        # Convert to radians
        angles_rad = np.radians(valid_data[param].values)
        weights = valid_data['weight'].values

        # Weighted circular mean
        sin_sum = np.sum(weights * np.sin(angles_rad))
        cos_sum = np.sum(weights * np.cos(angles_rad))

        mean_angle_rad = np.arctan2(sin_sum, cos_sum)
        mean_angle_deg = np.degrees(mean_angle_rad)

        # Convert to [0, 360) range
        return (mean_angle_deg + 360) % 360

    def _empty_result(self) -> Dict[str, float]:
        """Return empty result with NaN values"""
        return {
            'hs': np.nan,
            'tp': np.nan,
            'dp': np.nan,
            'wind_speed': np.nan,
            'wind_dir': np.nan,
            'n_stations': 0,
            'avg_distance_km': np.nan,
            'avg_time_diff_hours': np.nan
        }

    def interpolate_grid(
        self,
        lats: np.ndarray,
        lons: np.ndarray,
        target_time: datetime,
        observations: pd.DataFrame
    ) -> Dict[str, np.ndarray]:
        """
        Interpolate to a regular grid

        Args:
            lats: 1D array of latitudes
            lons: 1D array of longitudes
            target_time: Target datetime
            observations: DataFrame with buoy observations

        Returns:
            Dictionary with gridded arrays: {hs, tp, dp, wind_speed, wind_dir}
        """
        ny, nx = len(lats), len(lons)

        # Initialize output arrays
        hs_grid = np.full((ny, nx), np.nan)
        tp_grid = np.full((ny, nx), np.nan)
        dp_grid = np.full((ny, nx), np.nan)
        wind_speed_grid = np.full((ny, nx), np.nan)
        wind_dir_grid = np.full((ny, nx), np.nan)

        # Interpolate each grid point
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                result = self.interpolate_point(lat, lon, target_time, observations)

                hs_grid[i, j] = result['hs']
                tp_grid[i, j] = result['tp']
                dp_grid[i, j] = result['dp']
                wind_speed_grid[i, j] = result['wind_speed']
                wind_dir_grid[i, j] = result['wind_dir']

        return {
            'hs': hs_grid,
            'tp': tp_grid,
            'dp': dp_grid,
            'wind_speed': wind_speed_grid,
            'wind_dir': wind_dir_grid
        }


class SpatiotemporalInterpolator:
    """
    Combined spatiotemporal interpolator for buoy data

    Handles both spatial and temporal interpolation, with fallback strategies
    when buoy data is sparse or unavailable.
    """

    def __init__(
        self,
        idw_interpolator: Optional[IDWInterpolator] = None
    ):
        """
        Initialize interpolator

        Args:
            idw_interpolator: IDW interpolator instance (None = use defaults)
        """
        self.idw = idw_interpolator or IDWInterpolator()

    def get_deep_water_conditions(
        self,
        lat: float,
        lon: float,
        time: datetime,
        observations: pd.DataFrame,
        fallback_grib: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Get deep-water wave/wind conditions at a location and time

        Uses buoy interpolation if available, falls back to GRIB data.

        Args:
            lat: Target latitude
            lon: Target longitude
            time: Target datetime
            observations: DataFrame with buoy observations
            fallback_grib: Optional GRIB data dict to use if buoy interpolation fails

        Returns:
            Dictionary with: {hs, tp, dp, wind_speed, wind_dir, source}
        """
        # Try buoy interpolation
        result = self.idw.interpolate_point(lat, lon, time, observations)

        # Check if we have valid data
        if not np.isnan(result['hs']) and result['n_stations'] > 0:
            result['source'] = 'buoy_interpolation'
            logger.debug(
                f"Interpolated from {result['n_stations']} buoys "
                f"(avg distance: {result['avg_distance_km']:.1f} km)"
            )
            return result

        # Fall back to GRIB if available
        if fallback_grib:
            logger.debug("Buoy interpolation failed, using GRIB fallback")
            return {
                'hs': fallback_grib.get('hs', np.nan),
                'tp': fallback_grib.get('tp', np.nan),
                'dp': fallback_grib.get('dp', np.nan),
                'wind_speed': fallback_grib.get('wind_speed', np.nan),
                'wind_dir': fallback_grib.get('wind_dir', np.nan),
                'source': 'grib_fallback',
                'n_stations': 0
            }

        # No data available
        logger.warning(f"No data available for ({lat:.2f}, {lon:.2f}) at {time}")
        result['source'] = 'none'
        return result
