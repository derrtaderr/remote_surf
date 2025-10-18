"""
NDBC/NOAA buoy data loader

Fetches and caches buoy observations (Hs, Tp, Dp, wind) for use in
spatiotemporal interpolation and weak-label generation.

Data sources:
- NDBC (National Data Buoy Center): https://www.ndbc.noaa.gov/
- Realtime data: https://www.ndbc.noaa.gov/data/realtime2/
- Historical data: https://www.ndbc.noaa.gov/data/historical/stdmet/
"""

import requests
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BuoyStation:
    """Represents a single buoy station with metadata"""

    def __init__(
        self,
        station_id: str,
        lat: float,
        lon: float,
        name: str = "",
        type: str = "buoy"
    ):
        self.station_id = station_id
        self.lat = lat
        self.lon = lon
        self.name = name or f"Station {station_id}"
        self.type = type  # 'buoy', 'coastal', 'fixed'

    def __repr__(self) -> str:
        return f"BuoyStation({self.station_id}, {self.lat:.2f}, {self.lon:.2f})"


class BuoyDataLoader:
    """Load and cache NDBC buoy observations"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize buoy data loader

        Args:
            cache_dir: Directory to cache downloaded data (None = no caching)
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # NDBC API base URLs
        self.realtime_url = "https://www.ndbc.noaa.gov/data/realtime2/"
        self.stations_url = "https://www.ndbc.noaa.gov/data/stations/station_table.txt"

        self.stations: Dict[str, BuoyStation] = {}

    def load_stations(self, bbox: Optional[Tuple[float, float, float, float]] = None) -> Dict[str, BuoyStation]:
        """
        Load buoy station metadata

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat) to filter stations, or None for all

        Returns:
            Dictionary of {station_id: BuoyStation}
        """
        # For now, use hardcoded stations for Baja region
        # In production, would fetch from NDBC station list

        baja_stations = [
            BuoyStation("46047", 32.433, -119.533, "Tanner Bank - 180 NM West of San Diego", "buoy"),
            BuoyStation("46086", 32.491, -118.034, "San Clemente Basin - 43 NM WSW of San Clemente Island", "buoy"),
            BuoyStation("46221", 33.855, -119.053, "Santa Barbara - 38 NM West of Santa Barbara", "buoy"),
            BuoyStation("46025", 33.749, -119.053, "Santa Monica Basin - 33 NM WSW of Santa Monica", "buoy"),
            BuoyStation("46222", 33.618, -117.465, "San Pedro - 18 NM SW of Los Angeles", "buoy"),
            BuoyStation("46224", 33.168, -117.464, "Oceanside Offshore - 26 NM West of Oceanside", "buoy"),
            BuoyStation("46232", 32.930, -117.391, "Point Loma South - 13 NM SSW of Point Loma", "buoy"),
            BuoyStation("46235", 32.500, -117.426, "Outer Coronado - 25 NM Southwest of San Diego", "buoy"),
        ]

        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            self.stations = {
                s.station_id: s for s in baja_stations
                if min_lon <= s.lon <= max_lon and min_lat <= s.lat <= max_lat
            }
        else:
            self.stations = {s.station_id: s for s in baja_stations}

        logger.info(f"Loaded {len(self.stations)} buoy stations")
        return self.stations

    def fetch_realtime_data(
        self,
        station_id: str,
        data_type: str = "spec"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch realtime data from NDBC

        Args:
            station_id: NDBC station ID (e.g., '46086')
            data_type: Data type - 'spec' (spectral wave), 'stdmet' (standard meteorological)

        Returns:
            DataFrame with observations or None if fetch fails
        """
        # Data type file extensions
        ext_map = {
            "spec": ".spec",  # Spectral wave data (Hs, Tp, Dp)
            "stdmet": ".txt",  # Standard met (wind, pressure, temp)
        }

        url = f"{self.realtime_url}{station_id}{ext_map.get(data_type, '.txt')}"

        try:
            logger.info(f"Fetching {data_type} data from {url}")

            # Check cache first
            if self.cache_dir:
                cache_file = self.cache_dir / f"{station_id}_{data_type}_realtime.csv"
                if cache_file.exists():
                    # Check if cache is recent (< 1 hour old)
                    age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if age < timedelta(hours=1):
                        logger.info(f"Using cached data from {cache_file}")
                        return pd.read_csv(cache_file, parse_dates=['time'])

            # Fetch from NDBC
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse based on data type
            if data_type == "spec":
                df = self._parse_spec_data(response.text)
            else:
                df = self._parse_stdmet_data(response.text)

            # Cache the data
            if self.cache_dir and df is not None:
                cache_file = self.cache_dir / f"{station_id}_{data_type}_realtime.csv"
                df.to_csv(cache_file, index=False)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            return None

    def _parse_spec_data(self, text: str) -> Optional[pd.DataFrame]:
        """Parse NDBC spectral wave data format"""
        try:
            lines = text.strip().split('\n')

            # First two lines are headers
            if len(lines) < 3:
                return None

            # Skip header, parse data
            data = []
            for line in lines[2:]:
                parts = line.split()
                if len(parts) < 5:
                    continue

                # Format: YY MM DD hh mm WVHT SwH SwP WWH WWP SwD WWD STEEPNESS APD MWD
                try:
                    year = int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2])
                    hour = int(parts[3])
                    minute = int(parts[4])

                    # Convert 2-digit year to 4-digit
                    if year < 50:
                        year += 2000
                    else:
                        year += 1900

                    time = datetime(year, month, day, hour, minute)

                    # Extract wave parameters
                    wvht = float(parts[5]) if parts[5] != 'MM' else np.nan  # Significant wave height (m)
                    dpd = float(parts[6]) if len(parts) > 6 and parts[6] != 'MM' else np.nan  # Dominant wave period (s)
                    apd = float(parts[13]) if len(parts) > 13 and parts[13] != 'MM' else np.nan  # Average period (s)
                    mwd = float(parts[14]) if len(parts) > 14 and parts[14] != 'MM' else np.nan  # Mean wave direction (deg)

                    data.append({
                        'time': time,
                        'hs': wvht,
                        'tp': dpd if not np.isnan(dpd) else apd,  # Use dominant period, fallback to average
                        'dp': mwd
                    })
                except (ValueError, IndexError):
                    continue

            if not data:
                return None

            df = pd.DataFrame(data)
            return df

        except Exception as e:
            logger.error(f"Failed to parse spec data: {e}")
            return None

    def _parse_stdmet_data(self, text: str) -> Optional[pd.DataFrame]:
        """Parse NDBC standard meteorological data format"""
        try:
            lines = text.strip().split('\n')

            if len(lines) < 3:
                return None

            # Skip header, parse data
            data = []
            for line in lines[2:]:
                parts = line.split()
                if len(parts) < 8:
                    continue

                try:
                    year = int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2])
                    hour = int(parts[3])
                    minute = int(parts[4])

                    if year < 50:
                        year += 2000
                    else:
                        year += 1900

                    time = datetime(year, month, day, hour, minute)

                    # Wind speed (m/s) and direction (deg)
                    wdir = float(parts[5]) if parts[5] != 'MM' else np.nan
                    wspd = float(parts[6]) if parts[6] != 'MM' else np.nan

                    data.append({
                        'time': time,
                        'wind_dir': wdir,
                        'wind_speed': wspd
                    })
                except (ValueError, IndexError):
                    continue

            if not data:
                return None

            return pd.DataFrame(data)

        except Exception as e:
            logger.error(f"Failed to parse stdmet data: {e}")
            return None

    def get_observations(
        self,
        bbox: Tuple[float, float, float, float],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get all buoy observations within bbox and time range

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            start_time: Start of time range (None = last 48 hours)
            end_time: End of time range (None = now)

        Returns:
            DataFrame with columns: station_id, lat, lon, time, hs, tp, dp, wind_speed, wind_dir
        """
        # Load stations in bbox
        if not self.stations:
            self.load_stations(bbox)

        all_obs = []

        for station_id, station in self.stations.items():
            # Fetch wave data
            wave_df = self.fetch_realtime_data(station_id, "spec")
            wind_df = self.fetch_realtime_data(station_id, "stdmet")

            if wave_df is None:
                continue

            # Add station metadata
            wave_df['station_id'] = station_id
            wave_df['lat'] = station.lat
            wave_df['lon'] = station.lon

            # Merge wind data if available
            if wind_df is not None:
                wave_df = wave_df.merge(wind_df, on='time', how='left')

            # Filter by time range
            if start_time:
                wave_df = wave_df[wave_df['time'] >= start_time]
            if end_time:
                wave_df = wave_df[wave_df['time'] <= end_time]

            all_obs.append(wave_df)

        if not all_obs:
            logger.warning("No buoy observations found")
            return pd.DataFrame()

        result = pd.concat(all_obs, ignore_index=True)
        logger.info(f"Retrieved {len(result)} observations from {len(self.stations)} stations")

        return result

    def get_mock_observations(
        self,
        bbox: Tuple[float, float, float, float],
        num_hours: int = 48
    ) -> pd.DataFrame:
        """
        Generate mock buoy observations for development

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            num_hours: Number of hours of data to generate

        Returns:
            DataFrame with mock observations
        """
        # Load stations
        if not self.stations:
            self.load_stations(bbox)

        data = []
        now = datetime.now()

        for station_id, station in self.stations.items():
            for hour in range(num_hours):
                time = now - timedelta(hours=num_hours - hour)

                # Generate sinusoidal wave data
                hs = 2.0 + 0.8 * np.sin(hour * np.pi / 12)
                tp = 12.0 + 3.0 * np.cos(hour * np.pi / 18)
                dp = 225.0 + 15.0 * np.sin(hour * np.pi / 24)
                wind_speed = 5.0 + 3.0 * np.sin(hour * np.pi / 8)
                wind_dir = 45.0 + 20.0 * np.cos(hour * np.pi / 16)

                data.append({
                    'station_id': station_id,
                    'lat': station.lat,
                    'lon': station.lon,
                    'time': time,
                    'hs': hs,
                    'tp': tp,
                    'dp': dp,
                    'wind_speed': wind_speed,
                    'wind_dir': wind_dir
                })

        return pd.DataFrame(data)
