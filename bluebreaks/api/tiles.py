"""
Vector tile generation for wind and swell visualization
Generates MVT (Mapbox Vector Tiles) for efficient rendering
"""

import json
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import xarray as xr
from datetime import datetime


class WindTileGenerator:
    """Generate vector tiles for wind barbs"""

    def __init__(self, grib_path: Path):
        self.grib_path = grib_path
        self.ds = None

    def load_forecast(self, time: Optional[datetime] = None):
        """Load wind forecast data"""
        try:
            self.ds = xr.open_dataset(
                self.grib_path,
                engine='cfgrib',
                filter_by_keys={'typeOfLevel': 'surface'}
            )
        except Exception as e:
            print(f"Warning: Could not load GRIB file: {e}")
            self.ds = None

    def generate_wind_points(
        self,
        bbox: Tuple[float, float, float, float],
        spacing_deg: float = 0.5,
        time: Optional[datetime] = None
    ) -> dict:
        """
        Generate GeoJSON with wind barb points

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            spacing_deg: Grid spacing in degrees
            time: Forecast time

        Returns:
            GeoJSON FeatureCollection with wind data
        """
        min_lon, min_lat, max_lon, max_lat = bbox

        # Generate grid
        lons = np.arange(min_lon, max_lon, spacing_deg)
        lats = np.arange(min_lat, max_lat, spacing_deg)
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        features = []

        if self.ds is not None:
            try:
                # Extract wind components
                u10 = self.ds['u10'].sel(
                    longitude=slice(min_lon, max_lon),
                    latitude=slice(max_lat, min_lat)  # Reversed for north-up
                )
                v10 = self.ds['v10'].sel(
                    longitude=slice(min_lon, max_lon),
                    latitude=slice(max_lat, min_lat)
                )

                # Interpolate to grid points
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        try:
                            u_val = float(u10.interp(longitude=lon, latitude=lat).values)
                            v_val = float(v10.interp(longitude=lon, latitude=lat).values)

                            # Calculate speed and direction
                            speed = np.sqrt(u_val**2 + v_val**2)
                            direction = (np.degrees(np.arctan2(u_val, v_val)) + 360) % 360

                            features.append({
                                'type': 'Feature',
                                'geometry': {
                                    'type': 'Point',
                                    'coordinates': [lon, lat]
                                },
                                'properties': {
                                    'speed': round(speed, 2),
                                    'direction': round(direction, 1),
                                    'u': round(u_val, 2),
                                    'v': round(v_val, 2)
                                }
                            })
                        except Exception:
                            continue

            except Exception as e:
                print(f"Warning: Error extracting wind data: {e}")
                # Fall back to mock data
                self._generate_mock_wind(lon_grid, lat_grid, features)
        else:
            # Use mock data
            self._generate_mock_wind(lon_grid, lat_grid, features)

        return {
            'type': 'FeatureCollection',
            'features': features
        }

    def _generate_mock_wind(self, lon_grid, lat_grid, features):
        """Generate mock wind data for development"""
        for i in range(lon_grid.shape[0]):
            for j in range(lon_grid.shape[1]):
                lon = float(lon_grid[i, j])
                lat = float(lat_grid[i, j])

                # Mock: westerly wind with some variation
                base_speed = 5.0 + 3.0 * np.sin(lat * np.pi / 180)
                direction = 270 + 20 * np.sin(lon * np.pi / 180)

                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [lon, lat]
                    },
                    'properties': {
                        'speed': round(base_speed, 2),
                        'direction': round(direction % 360, 1),
                        'u': round(-base_speed * np.sin(np.radians(direction)), 2),
                        'v': round(-base_speed * np.cos(np.radians(direction)), 2)
                    }
                })


class SwellTileGenerator:
    """Generate vector tiles for swell arrows"""

    def __init__(self, grib_path: Path):
        self.grib_path = grib_path
        self.ds = None

    def load_forecast(self, time: Optional[datetime] = None):
        """Load wave forecast data"""
        try:
            self.ds = xr.open_dataset(
                self.grib_path,
                engine='cfgrib',
                filter_by_keys={'typeOfLevel': 'surface'}
            )
        except Exception as e:
            print(f"Warning: Could not load GRIB file: {e}")
            self.ds = None

    def generate_swell_arrows(
        self,
        bbox: Tuple[float, float, float, float],
        spacing_deg: float = 0.5,
        time: Optional[datetime] = None
    ) -> dict:
        """
        Generate GeoJSON with deep-water swell arrows

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            spacing_deg: Grid spacing in degrees
            time: Forecast time

        Returns:
            GeoJSON FeatureCollection with swell data
        """
        min_lon, min_lat, max_lon, max_lat = bbox

        # Generate grid
        lons = np.arange(min_lon, max_lon, spacing_deg)
        lats = np.arange(min_lat, max_lat, spacing_deg)
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        features = []

        if self.ds is not None:
            try:
                # Extract wave parameters (adjust variable names based on your GRIB)
                swh = self.ds.get('swh', self.ds.get('significant_height_of_wind_and_swell_waves'))
                mwd = self.ds.get('mwd', self.ds.get('mean_wave_direction'))
                mwp = self.ds.get('mwp', self.ds.get('mean_wave_period'))

                if swh is None or mwd is None:
                    raise ValueError("Wave variables not found in GRIB")

                # Select region
                swh_region = swh.sel(
                    longitude=slice(min_lon, max_lon),
                    latitude=slice(max_lat, min_lat)
                )
                mwd_region = mwd.sel(
                    longitude=slice(min_lon, max_lon),
                    latitude=slice(max_lat, min_lat)
                )
                mwp_region = mwp.sel(
                    longitude=slice(min_lon, max_lon),
                    latitude=slice(max_lat, min_lat)
                ) if mwp is not None else None

                # Interpolate to grid points
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        try:
                            hs = float(swh_region.interp(longitude=lon, latitude=lat).values)
                            direction = float(mwd_region.interp(longitude=lon, latitude=lat).values)
                            period = float(mwp_region.interp(longitude=lon, latitude=lat).values) if mwp_region is not None else 10.0

                            # Create arrow as LineString
                            # Arrow points in direction of wave travel (opposite of direction FROM)
                            arrow_dir = (direction + 180) % 360
                            arrow_rad = np.radians(arrow_dir)

                            # Arrow length scales with wave height (in degrees)
                            arrow_len = 0.15 * (hs / 3.0)  # Normalize to ~3m waves

                            end_lon = lon + arrow_len * np.sin(arrow_rad)
                            end_lat = lat + arrow_len * np.cos(arrow_rad)

                            features.append({
                                'type': 'Feature',
                                'geometry': {
                                    'type': 'LineString',
                                    'coordinates': [[lon, lat], [end_lon, end_lat]]
                                },
                                'properties': {
                                    'height': round(hs, 2),
                                    'period': round(period, 1),
                                    'direction': round(direction, 1),
                                    'dir_from': round(direction, 1),
                                    'dir_to': round(arrow_dir, 1)
                                }
                            })
                        except Exception:
                            continue

            except Exception as e:
                print(f"Warning: Error extracting swell data: {e}")
                self._generate_mock_swell(lon_grid, lat_grid, features)
        else:
            self._generate_mock_swell(lon_grid, lat_grid, features)

        return {
            'type': 'FeatureCollection',
            'features': features
        }

    def _generate_mock_swell(self, lon_grid, lat_grid, features):
        """Generate mock swell data for development"""
        for i in range(lon_grid.shape[0]):
            for j in range(lon_grid.shape[1]):
                lon = float(lon_grid[i, j])
                lat = float(lat_grid[i, j])

                # Mock: NW swell with variation
                hs = 1.5 + 0.5 * np.sin(lat * np.pi / 180)
                direction = 315 + 15 * np.sin(lon * np.pi / 180)
                period = 12.0 + 2.0 * np.cos(lat * np.pi / 180)

                arrow_dir = (direction + 180) % 360
                arrow_rad = np.radians(arrow_dir)
                arrow_len = 0.15 * (hs / 3.0)

                end_lon = lon + arrow_len * np.sin(arrow_rad)
                end_lat = lat + arrow_len * np.cos(arrow_rad)

                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [[lon, lat], [end_lon, end_lat]]
                    },
                    'properties': {
                        'height': round(hs, 2),
                        'period': round(period, 1),
                        'direction': round(direction, 1),
                        'dir_from': round(direction, 1),
                        'dir_to': round(arrow_dir, 1)
                    }
                })
