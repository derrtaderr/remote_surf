"""
Tests for weak label generation and feature extraction
"""

import pytest
import numpy as np
import pandas as pd

from bluebreaks.core.predict.labels import WeakLabelGenerator, FeatureExtractor


class TestWeakLabelGenerator:
    """Test weak label generator"""

    @pytest.fixture
    def generator(self):
        """Create label generator with default thresholds"""
        return WeakLabelGenerator(
            min_hs=1.0,
            max_hs=6.0,
            min_tp=10.0,
            min_exposure=0.3,
            min_physics_score=4.0,
            label_confidence_threshold=0.7
        )

    def test_perfect_conditions_labeled_positive(self, generator):
        """Perfect surf conditions should get positive label"""
        label, confidence = generator.generate_label(
            hs=2.0,  # Good height
            tp=14.0,  # Long period
            exposure=0.9,  # Great exposure
            wind_score=1.1,  # Offshore wind
            tide_score=0.95,  # Mid-high tide
            physics_score=7.5,  # High score
            shore_normal=270,  # West-facing
            wind_dir=90,  # East wind (offshore)
            wind_speed=5.0  # Light
        )

        assert label == 1  # Positive
        assert confidence > 0.7  # High confidence

    def test_poor_conditions_labeled_negative(self, generator):
        """Poor conditions should not get positive label"""
        label, confidence = generator.generate_label(
            hs=0.5,  # Too small
            tp=6.0,  # Short period
            exposure=0.1,  # Poor exposure
            wind_score=0.5,  # Onshore wind
            tide_score=0.7,  # Low tide
            physics_score=2.0,  # Low score
            shore_normal=270,
            wind_dir=270,  # West wind (onshore for west-facing)
            wind_speed=15.0  # Strong onshore
        )

        assert label == 0  # Not labeled positive
        assert confidence < 0.7  # Low confidence

    def test_onshore_wind_penalty(self, generator):
        """Strong onshore wind should lower confidence"""
        # Good conditions but onshore wind
        label, conf_onshore = generator.generate_label(
            hs=2.0,
            tp=14.0,
            exposure=0.9,
            wind_score=0.6,
            tide_score=0.95,
            physics_score=6.0,
            shore_normal=270,
            wind_dir=270,  # Onshore
            wind_speed=12.0  # Strong
        )

        # Same but offshore wind
        label2, conf_offshore = generator.generate_label(
            hs=2.0,
            tp=14.0,
            exposure=0.9,
            wind_score=1.1,
            tide_score=0.95,
            physics_score=6.0,
            shore_normal=270,
            wind_dir=90,  # Offshore
            wind_speed=5.0
        )

        assert conf_offshore > conf_onshore

    def test_generate_labels_batch(self, generator):
        """Test batch label generation"""
        candidates = [
            {
                'id': '1',
                'lat': 25.0,
                'lon': -111.0,
                'shore_normal': 270,
                'wave': {'hs': 2.0, 'tp': 14.0, 'dir': 225},
                'wind': {'speed': 5.0, 'dir': 90},
                'score': {'total': 7.0, 'components': {'expo': 0.9, 'wind': 1.1, 'tide': 0.95}}
            },
            {
                'id': '2',
                'lat': 25.1,
                'lon': -111.1,
                'shore_normal': 270,
                'wave': {'hs': 0.5, 'tp': 6.0, 'dir': 225},
                'wind': {'speed': 15.0, 'dir': 270},
                'score': {'total': 2.0, 'components': {'expo': 0.1, 'wind': 0.5, 'tide': 0.7}}
            }
        ]

        labels_df = generator.generate_labels_batch(candidates)

        assert len(labels_df) == 2
        assert 'label' in labels_df.columns
        assert 'confidence' in labels_df.columns

        # First should be positive, second negative
        assert labels_df.iloc[0]['label'] == 1
        assert labels_df.iloc[1]['label'] == 0


class TestFeatureExtractor:
    """Test feature extractor"""

    @pytest.fixture
    def extractor(self):
        """Create feature extractor"""
        return FeatureExtractor()

    @pytest.fixture
    def sample_candidate(self):
        """Create sample candidate"""
        return {
            'id': 'test_1',
            'lat': 25.0,
            'lon': -111.0,
            'shore_normal': 270,
            'curvature': 0.02,
            'depth': 10.0,
            'slope': 0.05,
            'wave': {
                'hs': 2.0,
                'tp': 14.0,
                'dir': 225,
                'nearshore_dir': 238
            },
            'wind': {
                'speed': 5.0,
                'dir': 90
            },
            'tide': {
                'height': 1.2
            },
            'score': {
                'total': 7.0,
                'components': {'expo': 0.9}
            },
            'anchorage': {
                'lee_shore_risk': 'low'
            },
            'remoteness': 0.6
        }

    def test_extract_basic_features(self, extractor, sample_candidate):
        """Test basic feature extraction"""
        features = extractor.extract_features(sample_candidate)

        # Check wave features
        assert 'hs' in features
        assert 'tp' in features
        assert features['hs'] == 2.0
        assert features['tp'] == 14.0

        # Check derived features
        assert 'wave_steepness' in features
        assert 'wave_energy' in features
        assert features['wave_steepness'] > 0
        assert features['wave_energy'] > 0

    def test_wind_features(self, extractor, sample_candidate):
        """Test wind-related features"""
        features = extractor.extract_features(sample_candidate)

        assert 'wind_speed' in features
        assert 'wind_angle' in features
        assert 'is_offshore' in features
        assert 'is_onshore' in features

        # Wind from 90° on 270° shore = offshore
        assert features['is_offshore'] == 1.0
        assert features['is_onshore'] == 0.0

    def test_geometric_features(self, extractor, sample_candidate):
        """Test geometric features"""
        features = extractor.extract_features(sample_candidate)

        assert 'curvature' in features
        assert 'is_point' in features
        assert 'depth' in features
        assert 'slope' in features
        assert 'depth_slope_ratio' in features

        assert features['curvature'] == abs(0.02)
        assert features['depth'] == 10.0

    def test_batch_extraction(self, extractor, sample_candidate):
        """Test batch feature extraction"""
        candidates = [sample_candidate] * 3  # 3 copies

        features_df = extractor.extract_features_batch(candidates)

        assert len(features_df) == 3
        assert 'hs' in features_df.columns
        assert 'tp' in features_df.columns
        assert 'id' in features_df.columns

    def test_refraction_angle_calculation(self, extractor):
        """Test refraction angle calculation"""
        candidate = {
            'id': 'test',
            'lat': 25.0,
            'lon': -111.0,
            'shore_normal': 270,
            'curvature': 0,
            'depth': 10,
            'slope': 0.05,
            'wave': {
                'hs': 2.0,
                'tp': 12.0,
                'dir': 225,  # SW
                'nearshore_dir': 250  # Refracted to W
            },
            'wind': {'speed': 5, 'dir': 90},
            'tide': {'height': 1.0},
            'score': {'total': 5.0, 'components': {'expo': 0.8}},
            'anchorage': {},
            'remoteness': 0.5
        }

        features = extractor.extract_features(candidate)

        # Refraction angle should be |250 - 225| = 25°
        assert features['refraction_angle'] == pytest.approx(25.0, abs=1.0)

    def test_point_break_detection(self, extractor):
        """Test point break detection"""
        # High curvature = point break
        point_candidate = {
            'id': 'point',
            'lat': 25.0,
            'lon': -111.0,
            'shore_normal': 270,
            'curvature': 0.05,  # High curvature
            'depth': 5,
            'slope': 0.1,
            'wave': {'hs': 2.0, 'tp': 12.0, 'dir': 225, 'nearshore_dir': 230},
            'wind': {'speed': 5, 'dir': 90},
            'tide': {'height': 1.0},
            'score': {'total': 6.0, 'components': {'expo': 0.9}},
            'anchorage': {},
            'remoteness': 0.7
        }

        features = extractor.extract_features(point_candidate)
        assert features['is_point'] == 1.0

        # Low curvature = beach break
        beach_candidate = point_candidate.copy()
        beach_candidate['curvature'] = 0.01  # Low curvature

        features2 = extractor.extract_features(beach_candidate)
        assert features2['is_point'] == 0.0
