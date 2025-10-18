"""
Tests for spatiotemporal interpolation module
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from bluebreaks.core.predict.interpolation import (
    haversine_distance,
    IDWInterpolator,
    SpatiotemporalInterpolator
)


class TestHaversineDistance:
    """Test haversine distance calculation"""

    def test_same_point(self):
        """Distance between same point should be 0"""
        dist = haversine_distance(25.0, -111.0, 25.0, -111.0)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_known_distance(self):
        """Test known distance (roughly 1 degree latitude ~ 111km)"""
        dist = haversine_distance(25.0, -111.0, 26.0, -111.0)
        assert dist == pytest.approx(111.0, rel=0.1)

    def test_longitude_distance(self):
        """Test longitude distance (varies with latitude)"""
        # At equator, 1 degree lon ~ 111km
        dist_eq = haversine_distance(0.0, 0.0, 0.0, 1.0)
        # At 60° latitude, 1 degree lon ~ 55.5km
        dist_60 = haversine_distance(60.0, 0.0, 60.0, 1.0)

        assert dist_eq > dist_60  # Higher latitude means shorter distances


class TestIDWInterpolator:
    """Test Inverse Distance Weighting interpolator"""

    @pytest.fixture
    def sample_observations(self):
        """Create sample buoy observations"""
        now = datetime.now()
        data = [
            {
                'station_id': 'A',
                'lat': 25.0,
                'lon': -111.0,
                'time': now,
                'hs': 2.0,
                'tp': 12.0,
                'dp': 225.0,
                'wind_speed': 5.0,
                'wind_dir': 45.0
            },
            {
                'station_id': 'B',
                'lat': 26.0,
                'lon': -110.0,
                'time': now,
                'hs': 2.5,
                'tp': 14.0,
                'dp': 230.0,
                'wind_speed': 6.0,
                'wind_dir': 50.0
            },
            {
                'station_id': 'C',
                'lat': 24.0,
                'lon': -112.0,
                'time': now,
                'hs': 1.8,
                'tp': 11.0,
                'dp': 220.0,
                'wind_speed': 4.5,
                'wind_dir': 40.0
            }
        ]
        return pd.DataFrame(data)

    def test_interpolation_at_station(self, sample_observations):
        """Interpolation at exact station location should return station values"""
        interp = IDWInterpolator(power=2.0, max_distance_km=500.0)

        result = interp.interpolate_point(
            target_lat=25.0,
            target_lon=-111.0,
            target_time=sample_observations['time'].iloc[0],
            observations=sample_observations
        )

        # Should be very close to station A values
        assert result['hs'] == pytest.approx(2.0, abs=0.1)
        assert result['tp'] == pytest.approx(12.0, abs=0.5)
        assert result['n_stations'] >= 1

    def test_interpolation_between_stations(self, sample_observations):
        """Interpolation between stations should give intermediate values"""
        interp = IDWInterpolator(power=2.0, max_distance_km=500.0)

        # Midpoint between A and B
        result = interp.interpolate_point(
            target_lat=25.5,
            target_lon=-110.5,
            target_time=sample_observations['time'].iloc[0],
            observations=sample_observations
        )

        # Should be between station A and B values
        assert 1.8 < result['hs'] < 2.5
        assert 11.0 < result['tp'] < 14.0

    def test_no_nearby_stations(self, sample_observations):
        """Interpolation far from any station should return NaN"""
        interp = IDWInterpolator(power=2.0, max_distance_km=50.0)  # Small radius

        result = interp.interpolate_point(
            target_lat=30.0,  # Far from all stations
            target_lon=-100.0,
            target_time=sample_observations['time'].iloc[0],
            observations=sample_observations
        )

        assert np.isnan(result['hs'])
        assert result['n_stations'] == 0

    def test_temporal_filtering(self, sample_observations):
        """Old observations should be filtered out"""
        interp = IDWInterpolator(max_time_hours=1.0)

        # Query 5 hours after observations
        future_time = sample_observations['time'].iloc[0] + timedelta(hours=5)

        result = interp.interpolate_point(
            target_lat=25.0,
            target_lon=-111.0,
            target_time=future_time,
            observations=sample_observations
        )

        assert result['n_stations'] == 0

    def test_circular_interpolation(self, sample_observations):
        """Test circular interpolation for directions"""
        interp = IDWInterpolator()

        # Interpolate direction (circular)
        result = interp.interpolate_point(
            target_lat=25.0,
            target_lon=-111.0,
            target_time=sample_observations['time'].iloc[0],
            observations=sample_observations
        )

        # Direction should be in valid range [0, 360)
        assert 0 <= result['dp'] < 360
        assert 0 <= result['wind_dir'] < 360


class TestSpatiotemporalInterpolator:
    """Test combined spatiotemporal interpolator"""

    @pytest.fixture
    def mock_observations(self):
        """Create mock observations"""
        now = datetime.now()
        return pd.DataFrame([
            {
                'station_id': 'TEST',
                'lat': 25.0,
                'lon': -111.0,
                'time': now,
                'hs': 2.0,
                'tp': 12.0,
                'dp': 225.0,
                'wind_speed': 5.0,
                'wind_dir': 45.0
            }
        ])

    def test_get_deep_water_conditions_with_buoys(self, mock_observations):
        """Test getting conditions from buoy data"""
        interp = SpatiotemporalInterpolator()

        result = interp.get_deep_water_conditions(
            lat=25.0,
            lon=-111.0,
            time=mock_observations['time'].iloc[0],
            observations=mock_observations
        )

        assert result['source'] == 'buoy_interpolation'
        assert result['hs'] == pytest.approx(2.0, abs=0.1)

    def test_fallback_to_grib(self):
        """Test fallback to GRIB when no buoy data"""
        interp = SpatiotemporalInterpolator()

        empty_obs = pd.DataFrame()
        fallback_grib = {
            'hs': 2.5,
            'tp': 13.0,
            'dp': 230.0,
            'wind_speed': 6.0,
            'wind_dir': 50.0
        }

        result = interp.get_deep_water_conditions(
            lat=25.0,
            lon=-111.0,
            time=datetime.now(),
            observations=empty_obs,
            fallback_grib=fallback_grib
        )

        assert result['source'] == 'grib_fallback'
        assert result['hs'] == 2.5

    def test_no_data_available(self):
        """Test behavior when no data available"""
        interp = SpatiotemporalInterpolator()

        empty_obs = pd.DataFrame()

        result = interp.get_deep_water_conditions(
            lat=25.0,
            lon=-111.0,
            time=datetime.now(),
            observations=empty_obs,
            fallback_grib=None
        )

        assert result['source'] == 'none'
        assert np.isnan(result['hs'])
