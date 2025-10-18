"""
Tide module for tidal window scoring

Provides simplified tide predictions and scoring based on:
- Nearest tide station lookup
- Simple harmonic predictions (or external API)
- Tide window scoring based on break type (beach vs reef/point)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json


class TideStation:
    """Represents a tide station with harmonic constituents"""

    def __init__(
        self,
        station_id: str,
        name: str,
        lat: float,
        lon: float,
        constituents: Optional[Dict] = None
    ):
        self.station_id = station_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.constituents = constituents or {}

    def predict_height(self, time: datetime) -> float:
        """
        Simple harmonic tide prediction

        For MVP, uses simplified M2 (principal lunar) constituent
        Real implementation would use full harmonic analysis
        """
        if not self.constituents:
            # Mock: simple sinusoidal tide (semi-diurnal ~12.4h period)
            hours_since_epoch = (time - datetime(2025, 1, 1)).total_seconds() / 3600
            # M2 period: 12.42 hours
            phase = (hours_since_epoch / 12.42) * 2 * np.pi
            # Amplitude ~1m, mean level 0m
            return 1.0 * np.sin(phase)

        # Real implementation would sum all constituents
        # height = mean + Σ(amplitude_i * cos(speed_i * t + phase_i))
        return 0.0

    def get_tide_range(self) -> float:
        """Get typical tidal range in meters"""
        if not self.constituents:
            return 2.0  # Mock: 2m range
        # Would calculate from constituents
        return 2.0


class TideStationDatabase:
    """Database of tide stations for lookup"""

    def __init__(self, stations_file: Optional[Path] = None):
        self.stations: List[TideStation] = []
        self.stations_file = stations_file

        if stations_file and stations_file.exists():
            self._load_stations(stations_file)
        else:
            self._load_mock_stations()

    def _load_stations(self, path: Path):
        """Load stations from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)
            for s in data['stations']:
                station = TideStation(
                    station_id=s['id'],
                    name=s['name'],
                    lat=s['lat'],
                    lon=s['lon'],
                    constituents=s.get('constituents')
                )
                self.stations.append(station)

    def _load_mock_stations(self):
        """Load mock stations for development"""
        # Mock stations for Baja region
        mock_stations = [
            TideStation("BAJ001", "Cabo San Lucas", 22.89, -109.91),
            TideStation("BAJ002", "La Paz", 24.14, -110.31),
            TideStation("BAJ003", "Bahía Magdalena", 24.64, -112.12),
            TideStation("BAJ004", "Punta Abreojos", 26.72, -113.58),
        ]
        self.stations.extend(mock_stations)

    def find_nearest_station(self, lat: float, lon: float) -> Optional[TideStation]:
        """Find nearest tide station to given coordinates"""
        if not self.stations:
            return None

        min_dist = float('inf')
        nearest = None

        for station in self.stations:
            # Simple euclidean distance (good enough for nearby stations)
            dist = np.sqrt((station.lat - lat)**2 + (station.lon - lon)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = station

        return nearest


class TideScorer:
    """Score tide conditions for surf quality"""

    @staticmethod
    def score_tide_for_break(
        tide_height: float,
        tide_range: float,
        slope: float,
        break_type: str = "beach"
    ) -> Tuple[float, str]:
        """
        Score tide suitability (0.7 - 1.1 multiplier)

        Args:
            tide_height: Current tide height in meters (relative to mean)
            tide_range: Tidal range in meters
            slope: Bottom slope (0-1)
            break_type: "beach", "point", or "reef"

        Returns:
            (score, label) where score is 0.7-1.1 and label is descriptive
        """
        # Normalize tide to 0-1 scale (0=low, 0.5=mid, 1=high)
        if tide_range > 0:
            normalized_tide = (tide_height + tide_range/2) / tide_range
            normalized_tide = np.clip(normalized_tide, 0, 1)
        else:
            normalized_tide = 0.5

        # Determine label
        if normalized_tide < 0.25:
            label = "low"
        elif normalized_tide < 0.45:
            label = "low-mid"
        elif normalized_tide < 0.65:
            label = "mid"
        elif normalized_tide < 0.85:
            label = "mid-high"
        else:
            label = "high"

        # Scoring logic based on break type and slope
        if break_type == "beach" or slope < 0.05:
            # Beach breaks prefer mid to high tide
            # Score highest at 0.6-0.8 (mid-high)
            if normalized_tide < 0.3:
                score = 0.7 + 0.2 * (normalized_tide / 0.3)  # 0.7-0.9
            elif normalized_tide < 0.8:
                score = 0.9 + 0.2 * ((normalized_tide - 0.3) / 0.5)  # 0.9-1.1
            else:
                score = 1.1 - 0.1 * ((normalized_tide - 0.8) / 0.2)  # 1.1-1.0

        elif break_type == "reef" or slope > 0.1:
            # Reef/point breaks are more tide-tolerant
            # Slight preference for mid-low to mid
            if normalized_tide < 0.2:
                score = 0.85  # Very low might be too shallow
            elif normalized_tide < 0.6:
                score = 1.05  # Low to mid is ideal
            elif normalized_tide < 0.8:
                score = 1.0   # Mid-high is good
            else:
                score = 0.95  # High is acceptable

        else:
            # Point breaks - broad window
            score = 0.95 + 0.1 * np.sin(normalized_tide * np.pi)  # 0.95-1.05

        return (float(np.clip(score, 0.7, 1.1)), label)

    @staticmethod
    def find_best_windows(
        times: List[datetime],
        scores: List[float],
        window_hours: int = 3,
        top_n: int = 3
    ) -> List[Dict]:
        """
        Find best time windows for surfing

        Args:
            times: List of forecast times
            scores: List of scores at each time
            window_hours: Window length in hours
            top_n: Number of best windows to return

        Returns:
            List of dicts with 'start', 'end', 'avg_score', 'peak_score'
        """
        if len(times) < 2:
            return []

        # Calculate time step
        time_step = (times[1] - times[0]).total_seconds() / 3600  # hours
        window_steps = int(window_hours / time_step)

        if window_steps <= 0:
            window_steps = 1

        # Calculate rolling average scores
        windows = []
        for i in range(len(scores) - window_steps + 1):
            window_scores = scores[i:i+window_steps]
            avg_score = np.mean(window_scores)
            peak_score = np.max(window_scores)

            windows.append({
                'start': times[i],
                'end': times[i + window_steps - 1],
                'avg_score': float(avg_score),
                'peak_score': float(peak_score),
                'duration_hours': window_hours
            })

        # Sort by average score and return top N
        windows_sorted = sorted(windows, key=lambda w: w['avg_score'], reverse=True)
        return windows_sorted[:top_n]


class TideModule:
    """Main tide module for integration with scanner"""

    def __init__(self, stations_file: Optional[Path] = None):
        self.db = TideStationDatabase(stations_file)
        self.scorer = TideScorer()

    def get_tide_info(
        self,
        lat: float,
        lon: float,
        time: datetime,
        slope: float = 0.05
    ) -> Dict:
        """
        Get tide information for a location and time

        Returns:
            Dict with 'height', 'range', 'score', 'label', 'station_name', 'distance_km'
        """
        # Find nearest station
        station = self.db.find_nearest_station(lat, lon)

        if not station:
            # No station available - return neutral
            return {
                'height': 0.0,
                'range': 2.0,
                'score': 1.0,
                'label': 'unknown',
                'station_name': 'None',
                'distance_km': None
            }

        # Calculate distance to station
        dist = np.sqrt((station.lat - lat)**2 + (station.lon - lon)**2) * 111  # rough km

        # Get tide prediction
        tide_height = station.predict_height(time)
        tide_range = station.get_tide_range()

        # Score tide
        score, label = self.scorer.score_tide_for_break(
            tide_height, tide_range, slope
        )

        return {
            'height': round(tide_height, 2),
            'range': round(tide_range, 1),
            'score': round(score, 2),
            'label': label,
            'station_name': station.name,
            'distance_km': round(dist, 1)
        }

    def get_tide_series(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        hours: int = 120,  # 5 days
        interval_hours: int = 1,
        slope: float = 0.05
    ) -> List[Dict]:
        """
        Get tide time series for forecast period

        Returns:
            List of dicts with 'time', 'height', 'score', 'label'
        """
        station = self.db.find_nearest_station(lat, lon)

        if not station:
            return []

        tide_series = []
        current_time = start_time

        for _ in range(int(hours / interval_hours)):
            tide_height = station.predict_height(current_time)
            tide_range = station.get_tide_range()
            score, label = self.scorer.score_tide_for_break(
                tide_height, tide_range, slope
            )

            tide_series.append({
                'time': current_time.isoformat(),
                'height': round(tide_height, 2),
                'score': round(score, 2),
                'label': label
            })

            current_time += timedelta(hours=interval_hours)

        return tide_series
