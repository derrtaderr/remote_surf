"""
Weak-label generator for PU (Positive-Unlabeled) learning

Generates soft positive labels based on physics heuristics to train
the ML model. Uses thresholds on physics score components to identify
likely surfable conditions.

The weak labels are noisy but allow us to learn patterns without
having ground-truth labels for every location.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class WeakLabelGenerator:
    """
    Generate weak labels for surf quality based on physics heuristics

    A point is labeled as a soft positive if it meets minimum thresholds
    for multiple conditions (exposure, wave height, period, wind, tide).
    """

    def __init__(
        self,
        min_hs: float = 1.0,
        max_hs: float = 6.0,
        min_tp: float = 10.0,
        min_exposure: float = 0.3,
        max_onshore_wind: float = 8.0,
        min_physics_score: float = 4.0,
        label_confidence_threshold: float = 0.7
    ):
        """
        Initialize weak label generator

        Args:
            min_hs: Minimum wave height (m) for surfable conditions
            max_hs: Maximum wave height (m) for safe surfing
            min_tp: Minimum period (s) for quality waves
            min_exposure: Minimum exposure factor (0-1)
            max_onshore_wind: Maximum onshore wind speed (m/s)
            min_physics_score: Minimum physics score (0-10) for positive label
            label_confidence_threshold: Confidence threshold for weak labels (0-1)
        """
        self.min_hs = min_hs
        self.max_hs = max_hs
        self.min_tp = min_tp
        self.min_exposure = min_exposure
        self.max_onshore_wind = max_onshore_wind
        self.min_physics_score = min_physics_score
        self.label_confidence_threshold = label_confidence_threshold

    def generate_label(
        self,
        hs: float,
        tp: float,
        exposure: float,
        wind_score: float,
        tide_score: float,
        physics_score: float,
        shore_normal: float,
        wind_dir: float,
        wind_speed: float
    ) -> Tuple[int, float]:
        """
        Generate weak label for a single observation

        Args:
            hs: Significant wave height (m)
            tp: Peak period (s)
            exposure: Exposure factor (0-1)
            wind_score: Wind score component (0-1.5)
            tide_score: Tide score component (0.7-1.1)
            physics_score: Overall physics score (0-10)
            shore_normal: Shore normal direction (degrees)
            wind_dir: Wind direction (degrees FROM)
            wind_speed: Wind speed (m/s)

        Returns:
            Tuple of (label, confidence) where:
                label: 1 (positive), 0 (negative/unlabeled)
                confidence: 0-1 indicating label confidence
        """
        # Calculate wind angle relative to shore
        wind_angle = abs((wind_dir - shore_normal) % 360)
        if wind_angle > 180:
            wind_angle = 360 - wind_angle

        # Onshore wind (bad for surfing)
        is_onshore = wind_angle > 135

        # Check basic conditions
        conditions = []

        # Condition 1: Wave height in reasonable range
        if self.min_hs <= hs <= self.max_hs:
            conditions.append(1.0)
        else:
            conditions.append(0.0)

        # Condition 2: Good period (long period = better waves)
        if tp >= self.min_tp:
            conditions.append(min((tp - self.min_tp) / 5.0, 1.0))  # Saturates at Tp=15s
        else:
            conditions.append(0.0)

        # Condition 3: Sufficient exposure
        if exposure >= self.min_exposure:
            conditions.append(exposure)
        else:
            conditions.append(0.0)

        # Condition 4: Wind compatible (offshore or light onshore)
        if not is_onshore:
            # Offshore/cross-shore wind: good
            conditions.append(1.0)
        elif wind_speed < self.max_onshore_wind:
            # Light onshore wind: acceptable
            conditions.append(0.5)
        else:
            # Strong onshore wind: bad
            conditions.append(0.0)

        # Condition 5: Tide OK (based on tide score)
        if tide_score >= 0.85:  # Mid-high tide range
            conditions.append(1.0)
        elif tide_score >= 0.75:
            conditions.append(0.7)
        else:
            conditions.append(0.3)

        # Condition 6: Overall physics score
        if physics_score >= self.min_physics_score:
            score_factor = min((physics_score - self.min_physics_score) / 3.0, 1.0)
            conditions.append(score_factor)
        else:
            conditions.append(0.0)

        # Compute label confidence as geometric mean of conditions
        confidence = np.prod(conditions) ** (1.0 / len(conditions))

        # Assign label based on confidence threshold
        if confidence >= self.label_confidence_threshold:
            label = 1  # Positive (likely surfable)
        else:
            label = 0  # Unlabeled (may or may not be surfable)

        return label, float(confidence)

    def generate_labels_batch(
        self,
        candidates: List[Dict]
    ) -> pd.DataFrame:
        """
        Generate weak labels for a batch of candidates

        Args:
            candidates: List of candidate dicts with wave/wind/tide/score data

        Returns:
            DataFrame with columns: id, label, confidence, features
        """
        labels_data = []

        for candidate in candidates:
            # Extract parameters
            hs = candidate.get('wave', {}).get('hs', 0)
            tp = candidate.get('wave', {}).get('tp', 0)
            wave_dir = candidate.get('wave', {}).get('dir', 0)
            wind_speed = candidate.get('wind', {}).get('speed', 0)
            wind_dir = candidate.get('wind', {}).get('dir', 0)
            shore_normal = candidate.get('shore_normal', 0)

            # Get score components
            score_data = candidate.get('score', {})
            components = score_data.get('components', {})
            physics_score = score_data.get('total', 0)

            # Calculate exposure
            exposure = components.get('expo', 0)
            wind_score = components.get('wind', 1.0)
            tide_score = components.get('tide', 1.0)

            # Generate label
            label, confidence = self.generate_label(
                hs=hs,
                tp=tp,
                exposure=exposure,
                wind_score=wind_score,
                tide_score=tide_score,
                physics_score=physics_score,
                shore_normal=shore_normal,
                wind_dir=wind_dir,
                wind_speed=wind_speed
            )

            labels_data.append({
                'id': candidate.get('id', ''),
                'lat': candidate.get('lat', 0),
                'lon': candidate.get('lon', 0),
                'label': label,
                'confidence': confidence,
                'hs': hs,
                'tp': tp,
                'exposure': exposure,
                'shore_normal': shore_normal,
                'physics_score': physics_score,
                'wind_speed': wind_speed,
                'wind_dir': wind_dir
            })

        df = pd.DataFrame(labels_data)

        logger.info(
            f"Generated {len(df)} labels: "
            f"{(df['label'] == 1).sum()} positive, "
            f"{(df['label'] == 0).sum()} unlabeled "
            f"(avg confidence: {df['confidence'].mean():.3f})"
        )

        return df


class FeatureExtractor:
    """
    Extract features for ML model from candidate data

    Converts raw wave/wind/tide data into features suitable for
    gradient boosting models.
    """

    def __init__(self):
        pass

    def extract_features(self, candidate: Dict) -> Dict[str, float]:
        """
        Extract feature vector from candidate

        Args:
            candidate: Candidate dict with all parameters

        Returns:
            Dictionary of features
        """
        # Wave features
        wave = candidate.get('wave', {})
        hs = wave.get('hs', 0)
        tp = wave.get('tp', 0)
        wave_dir = wave.get('dir', 0)
        nearshore_dir = wave.get('nearshore_dir', wave_dir)

        # Wind features
        wind = candidate.get('wind', {})
        wind_speed = wind.get('speed', 0)
        wind_dir = wind.get('dir', 0)

        # Geometric features
        shore_normal = candidate.get('shore_normal', 0)
        curvature = candidate.get('curvature', 0)
        depth = candidate.get('depth', 10)
        slope = candidate.get('slope', 0.05)

        # Calculate derived features
        wave_angle = abs((wave_dir - shore_normal) % 360)
        if wave_angle > 180:
            wave_angle = 360 - wave_angle

        wind_angle = abs((wind_dir - shore_normal) % 360)
        if wind_angle > 180:
            wind_angle = 360 - wind_angle

        refraction_angle = abs(nearshore_dir - wave_dir)

        # Tide features
        tide = candidate.get('tide', {})
        tide_height = tide.get('height', 0)

        # Anchorage features (may indicate remote/quality spots)
        anchorage = candidate.get('anchorage', {})
        remoteness = candidate.get('remoteness', 0)

        features = {
            # Wave features
            'hs': hs,
            'tp': tp,
            'wave_steepness': hs / (tp**2) if tp > 0 else 0,
            'wave_energy': hs**2 * tp,  # Proxy for wave energy
            'wave_angle': wave_angle,
            'refraction_angle': refraction_angle,

            # Wind features
            'wind_speed': wind_speed,
            'wind_angle': wind_angle,
            'is_offshore': 1.0 if wind_angle < 90 else 0.0,
            'is_onshore': 1.0 if wind_angle > 135 else 0.0,

            # Geometric features
            'curvature': abs(curvature),
            'is_point': 1.0 if abs(curvature) > 0.03 else 0.0,
            'depth': depth,
            'slope': slope,
            'depth_slope_ratio': depth / (slope + 0.001),

            # Tide features
            'tide_height': tide_height,

            # Quality indicators
            'remoteness': remoteness,
            'lee_shore_risk': 1.0 if anchorage.get('lee_shore_risk') == 'high' else 0.0,

            # Physics score components (can help ML learn residuals)
            'physics_score': candidate.get('score', {}).get('total', 0),
            'exposure': candidate.get('score', {}).get('components', {}).get('expo', 0)
        }

        return features

    def extract_features_batch(self, candidates: List[Dict]) -> pd.DataFrame:
        """
        Extract features for multiple candidates

        Args:
            candidates: List of candidate dicts

        Returns:
            DataFrame with feature vectors
        """
        features_list = []

        for candidate in candidates:
            features = self.extract_features(candidate)
            features['id'] = candidate.get('id', '')
            features['lat'] = candidate.get('lat', 0)
            features['lon'] = candidate.get('lon', 0)
            features_list.append(features)

        return pd.DataFrame(features_list)
