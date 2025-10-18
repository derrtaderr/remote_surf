"""
Anchorage suitability analysis

Evaluates potential anchorages near surf candidates based on:
- Depth (3-15m ideal for cruising boats)
- Distance from candidate (0.5-1nm ideal)
- Fetch/exposure to wind
- Lee shore risk
- Other hazards
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union


def evaluate_anchorage(
    candidate_lat: float,
    candidate_lon: float,
    candidate_depth: float,
    wind_dir: float,
    shore_normal: float,
    land_polygon: Optional[Polygon] = None
) -> Dict:
    """
    Evaluate anchorage suitability near a surf candidate

    Args:
        candidate_lat: Candidate latitude
        candidate_lon: Candidate longitude
        candidate_depth: Depth at candidate (m)
        wind_dir: Wind direction (degrees FROM)
        shore_normal: Shore normal (degrees TO sea)
        land_polygon: Land polygon for lee shore analysis

    Returns:
        Dict with anchorage metrics and flags
    """
    # Estimate anchorage location (offshore from candidate)
    # Typically 0.5-1nm offshore
    distance_nm = 0.7  # nautical miles
    distance_deg = distance_nm / 60  # rough conversion

    # Anchor offshore along shore normal direction
    anchor_lat = candidate_lat + distance_deg * np.cos(np.radians(shore_normal))
    anchor_lon = candidate_lon + distance_deg * np.sin(np.radians(shore_normal))

    # Estimate depth at anchorage (typically deeper than surf zone)
    # Simplification: anchor depth ≈ candidate depth + 3-8m
    anchor_depth = candidate_depth + 5.0

    # Check depth window (3-15m ideal)
    depth_suitable = 3.0 <= anchor_depth <= 15.0
    if anchor_depth < 3.0:
        depth_flag = "too_shallow"
    elif anchor_depth > 15.0:
        depth_flag = "too_deep"
    else:
        depth_flag = "ok"

    # Assess lee shore risk
    # Lee shore = wind blowing FROM sea TO land (dangerous)
    lee_shore_risk = assess_lee_shore_risk(wind_dir, shore_normal)

    # Assess fetch/protection
    # Protected if wind is offshore or if there's land shelter
    fetch_assessment = assess_fetch(
        wind_dir, shore_normal, land_polygon,
        Point(anchor_lon, anchor_lat) if land_polygon else None
    )

    # Dinghy landing assessment
    # Prefer calm conditions and gentle beach
    dinghy_landing = assess_dinghy_landing(
        candidate_depth, wind_dir, shore_normal
    )

    # Generate flags
    flags = []
    if lee_shore_risk == "high":
        flags.append("lee shore risk: high")
    elif lee_shore_risk == "moderate":
        flags.append("lee shore risk: moderate")

    if depth_flag == "too_shallow":
        flags.append("anchorage: too shallow")
    elif depth_flag == "too_deep":
        flags.append("anchorage: deep (>15m)")

    if dinghy_landing == "difficult":
        flags.append("dinghy landing: difficult")
    elif dinghy_landing == "moderate":
        flags.append("dinghy landing: moderate")

    if candidate_depth < 2.0:
        flags.append("reef nearby")

    return {
        "distance_nm": round(distance_nm, 1),
        "depth_m": round(anchor_depth, 1),
        "depth_suitable": depth_suitable,
        "lee_shore_risk": lee_shore_risk,
        "fetch": fetch_assessment,
        "dinghy_landing": dinghy_landing,
        "flags": flags,
    }


def assess_lee_shore_risk(wind_dir: float, shore_normal: float) -> str:
    """
    Assess lee shore risk based on wind direction

    Args:
        wind_dir: Wind direction (degrees FROM)
        shore_normal: Shore normal (degrees TO sea)

    Returns:
        "low", "moderate", or "high"
    """
    # Wind angle relative to shore
    # If wind is FROM sea (opposite to shore normal), that's onshore = lee shore
    wind_angle = (wind_dir - shore_normal) % 360
    if wind_angle > 180:
        wind_angle -= 360

    # Onshore wind (lee shore) is dangerous
    # wind_angle ≈ 180 means wind FROM sea TO land
    if 135 <= abs(wind_angle) <= 180:
        return "high"
    elif 90 <= abs(wind_angle) < 135:
        return "moderate"
    else:
        return "low"


def assess_fetch(
    wind_dir: float,
    shore_normal: float,
    land_polygon: Optional[Polygon],
    anchor_point: Optional[Point]
) -> str:
    """
    Assess fetch and protection from wind

    Args:
        wind_dir: Wind direction (degrees FROM)
        shore_normal: Shore normal
        land_polygon: Land polygon for shelter assessment
        anchor_point: Anchorage point

    Returns:
        Description of fetch/protection
    """
    # Calculate wind angle relative to shore
    wind_angle = (wind_dir - shore_normal) % 360
    if wind_angle > 180:
        wind_angle -= 360

    # Offshore wind = protected
    if abs(wind_angle) < 45:
        # Wind blowing offshore
        return "protected (offshore wind)"

    # Check if land provides shelter
    # TODO: Implement ray-tracing for land shelter
    # For now, simplified logic
    if abs(wind_angle) < 90:
        return "some protection"
    else:
        return "exposed"


def assess_dinghy_landing(
    depth: float,
    wind_dir: float,
    shore_normal: float
) -> str:
    """
    Assess difficulty of dinghy landing

    Args:
        depth: Depth at surf candidate
        wind_dir: Wind direction
        shore_normal: Shore normal

    Returns:
        "easy", "moderate", or "difficult"
    """
    # Steep/deep = rocky shore = difficult landing
    if depth < 2.0:
        landing_difficulty = "difficult"  # Shallow reef
    elif depth < 5.0:
        landing_difficulty = "moderate"  # Shallow beach
    else:
        landing_difficulty = "easy"  # Deeper beach

    # Onshore wind makes landing harder
    wind_angle = abs((wind_dir - shore_normal) % 360)
    if wind_angle > 180:
        wind_angle = 360 - wind_angle

    if wind_angle > 135:
        # Onshore wind
        if landing_difficulty == "easy":
            landing_difficulty = "moderate"
        else:
            landing_difficulty = "difficult"

    return landing_difficulty


def calculate_remoteness(
    lat: float,
    lon: float,
    nearest_road_km: Optional[float] = None,
    nearest_marina_km: Optional[float] = None
) -> float:
    """
    Calculate remoteness score (0-1, 1 = very remote)

    Args:
        lat: Latitude
        lon: Longitude
        nearest_road_km: Distance to nearest road (if available)
        nearest_marina_km: Distance to nearest marina (if available)

    Returns:
        Remoteness score (0-1)
    """
    # Placeholder implementation
    # Would use OSM road/marina data + night lights

    if nearest_road_km is None or nearest_marina_km is None:
        # Mock: Use latitude as proxy (higher latitude = more remote in some regions)
        return np.clip(abs(lat) / 60.0, 0.0, 1.0)

    # Distance-based remoteness
    road_score = np.clip(nearest_road_km / 50.0, 0.0, 1.0)
    marina_score = np.clip(nearest_marina_km / 100.0, 0.0, 1.0)

    return (road_score + marina_score) / 2.0
