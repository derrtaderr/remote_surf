"""
SurfScore calculation engine

Implements the physics-based scoring model from PRD:
SurfScore = Base × Expo^γ × Refract × Wind × Tide × Period × Quality
"""

import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Scoring parameters
HREF = 1.8  # Reference wave height (m)
GAMMA_EXPO = 1.2  # Exposure exponent
TREF = 10.0  # Reference period (s)


def score_wave_height(Hs: float, href: float = HREF) -> float:
    """
    Base score from wave height

    Base = min(1, Hs / href)

    Args:
        Hs: Significant wave height (m)
        href: Reference height (default 1.8m)

    Returns:
        Base score (0-1)
    """
    return min(1.0, Hs / href)


def score_exposure(exposure: float, gamma: float = GAMMA_EXPO) -> float:
    """
    Score from wave exposure angle

    Expo = exposure^γ

    Args:
        exposure: Exposure factor (0-1) from physics.calculate_exposure()
        gamma: Exponent for sharper falloff

    Returns:
        Exposure score (0-1)
    """
    return exposure**gamma


def score_refraction(refraction_coeff: float, shoaling_coeff: float) -> float:
    """
    Score from wave refraction/shoaling

    Refract = shoaling_coeff × refraction_coeff

    Args:
        refraction_coeff: Refraction coefficient (typically 0.8-1.2)
        shoaling_coeff: Shoaling coefficient (typically 1.0-2.0)

    Returns:
        Refraction score (0.5-2.0, clamped)
    """
    score = shoaling_coeff * refraction_coeff
    return np.clip(score, 0.5, 2.0)


def score_wind(wind_speed: float, wind_dir: float, shore_normal: float) -> float:
    """
    Score from wind conditions

    Offshore/cross-off winds score higher (>1.0)
    Onshore winds score lower (<1.0)

    Args:
        wind_speed: Wind speed (m/s)
        wind_dir: Wind direction (degrees, meteorological - FROM)
        shore_normal: Shore normal (degrees - TO sea)

    Returns:
        Wind score (0.5-1.2)
    """
    # Angle between wind and shore normal
    # Wind FROM wind_dir, shore normal TO sea
    wind_angle = (wind_dir - shore_normal + 180) % 360

    if wind_angle > 180:
        wind_angle -= 360

    # Offshore: wind blowing FROM land TO sea (angle ≈ 180°)
    # Onshore: wind blowing FROM sea TO land (angle ≈ 0°)

    if abs(wind_angle) > 135:
        # Offshore
        base_score = 1.15
    elif abs(wind_angle) > 90:
        # Cross-offshore
        base_score = 1.10
    elif abs(wind_angle) > 45:
        # Cross
        base_score = 1.0
    else:
        # Onshore
        base_score = 0.85

    # Penalize strong onshore winds
    if abs(wind_angle) < 90 and wind_speed > 6:  # ~12 kt
        penalty = 0.95 - (wind_speed - 6) * 0.02
        base_score *= max(0.5, penalty)

    return np.clip(base_score, 0.5, 1.2)


def score_period(Tp: float, tref: float = TREF) -> float:
    """
    Score from wave period

    Period = clamp(Tp / tref, 0.7, 1.3)
    Longer period = better quality

    Args:
        Tp: Peak period (s)
        tref: Reference period (default 10s)

    Returns:
        Period score (0.7-1.3)
    """
    score = Tp / tref
    return np.clip(score, 0.7, 1.3)


def score_tide(
    tide_level: float, slope: float, beach_type: str = "beach"
) -> float:
    """
    Score from tide level (placeholder - needs tide module)

    Beach: prefer mid-high tide
    Reef/Point: broader window

    Args:
        tide_level: Tide level in meters (0 = MSL)
        slope: Bathymetric slope
        beach_type: "beach", "reef", or "point"

    Returns:
        Tide score (0.7-1.1)
    """
    # Placeholder implementation
    # TODO: Implement proper tide windowing

    if beach_type == "beach":
        # Prefer mid to high tide
        if 0.5 <= tide_level <= 1.5:
            return 1.1
        elif -0.5 <= tide_level <= 0.5:
            return 1.0
        else:
            return 0.85

    # Reef/point: less sensitive to tide
    return 1.0


def score_quality(curvature: float, slope: float, substrate: str = "unknown") -> float:
    """
    Quality adjustment based on break characteristics

    Point/reef with good substrate: 1.1-1.2
    Beach: 0.9-1.0
    Unknown: 1.0

    Args:
        curvature: Coastline curvature
        slope: Bathymetric slope
        substrate: Seabed type ("sand", "rock", "reef", "unknown")

    Returns:
        Quality score (0.8-1.2)
    """
    score = 1.0

    # Curvature bonus (point/reef)
    if curvature > 0.05:
        score += 0.1

    # Slope bonus (steep = more powerful)
    if slope > 0.15:
        score += 0.05
    elif slope < 0.03:
        score -= 0.1

    # Substrate bonus
    if substrate in ["reef", "rock"]:
        score += 0.05
    elif substrate == "sand":
        score += 0.0

    return np.clip(score, 0.8, 1.2)


def calculate_surf_score(
    Hs: float,
    Tp: float,
    wave_dir: float,
    wind_speed: float,
    wind_dir: float,
    shore_normal: float,
    exposure: float,
    refraction_coeff: float,
    shoaling_coeff: float,
    curvature: float,
    slope: float,
    tide_level: float = 0.0,
    substrate: str = "unknown",
) -> Dict[str, float]:
    """
    Calculate complete SurfScore

    Args:
        Hs: Significant wave height (m)
        Tp: Peak period (s)
        wave_dir: Wave direction (degrees)
        wind_speed: Wind speed (m/s)
        wind_dir: Wind direction (degrees)
        shore_normal: Shore normal direction (degrees)
        exposure: Wave exposure factor (0-1)
        refraction_coeff: Refraction coefficient
        shoaling_coeff: Shoaling coefficient
        curvature: Coastline curvature
        slope: Bathymetric slope
        tide_level: Tide level (m, optional)
        substrate: Seabed type (optional)

    Returns:
        Dictionary with total score and components
    """
    # Component scores
    base = score_wave_height(Hs)
    expo = score_exposure(exposure)
    refract = score_refraction(refraction_coeff, shoaling_coeff)
    wind = score_wind(wind_speed, wind_dir, shore_normal)
    tide = score_tide(tide_level, slope)
    period = score_period(Tp)
    quality = score_quality(curvature, slope, substrate)

    # Total score (multiplicative)
    total = base * expo * refract * wind * tide * period * quality

    # Normalize to 0-10 scale
    total_scaled = total * 10.0

    return {
        "total": np.clip(total_scaled, 0.0, 10.0),
        "components": {
            "base": base,
            "expo": expo,
            "refract": refract,
            "wind": wind,
            "tide": tide,
            "period": period,
            "quality": quality,
        },
    }


def score_batch(candidates: list[Dict[str, Any]], wave_data: Dict, wind_data: Dict) -> list[Dict]:
    """
    Score multiple candidates in batch

    Args:
        candidates: List of candidate dictionaries
        wave_data: Wave forecast data
        wind_data: Wind forecast data

    Returns:
        Candidates with scores added
    """
    # TODO: Implement batch scoring with vectorization
    logger.warning("Batch scoring not yet fully implemented")

    for candidate in candidates:
        # Placeholder: assign mock score
        candidate["score"] = {
            "total": 5.0,
            "components": {
                "base": 0.8,
                "expo": 0.9,
                "refract": 1.1,
                "wind": 1.05,
                "tide": 1.0,
                "period": 1.2,
                "quality": 1.0,
            },
        }

    return candidates
