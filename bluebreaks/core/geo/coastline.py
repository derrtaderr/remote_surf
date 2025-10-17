"""
Coastline segmentation and analysis

Generates candidate surf points along coastline with:
- Shore normal vectors (perpendicular to coast)
- Curvature (proxy for point/reef vs beach)
- Spacing control (300-600m intervals)
"""

import numpy as np
from shapely.geometry import LineString, Point
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


def segment_coastline(
    coastline: LineString, spacing_m: float = 500.0
) -> List[Tuple[float, float]]:
    """
    Segment coastline into evenly-spaced points

    Args:
        coastline: Coastline as LineString (WGS84)
        spacing_m: Target spacing in meters

    Returns:
        List of (lon, lat) tuples
    """
    # Convert spacing to degrees (approximate)
    # 1 degree latitude ≈ 111 km
    # 1 degree longitude varies with latitude
    mean_lat = np.mean([coord[1] for coord in coastline.coords])
    spacing_deg_lat = spacing_m / 111320.0
    spacing_deg_lon = spacing_m / (111320.0 * np.cos(np.radians(mean_lat)))
    spacing_deg = np.mean([spacing_deg_lat, spacing_deg_lon])

    # Calculate number of segments
    length_deg = coastline.length
    num_points = max(int(length_deg / spacing_deg), 2)

    # Generate points along line
    points = []
    for i in range(num_points):
        fraction = i / (num_points - 1) if num_points > 1 else 0
        point = coastline.interpolate(fraction, normalized=True)
        points.append((point.x, point.y))

    logger.info(f"Segmented coastline into {len(points)} points ({spacing_m}m spacing)")
    return points


def compute_shore_normal(
    coastline: LineString, point: Tuple[float, float], window_deg: float = 0.01
) -> float:
    """
    Compute shore normal (perpendicular to coast) at a point

    Args:
        coastline: Coastline as LineString
        point: (lon, lat) point on coastline
        window_deg: Window size for local tangent estimation

    Returns:
        Shore normal direction in degrees (0-360, oceanographic convention)
    """
    lon, lat = point
    p = Point(lon, lat)

    # Find nearest point on coastline
    distance_on_line = coastline.project(p)

    # Get points before and after for tangent calculation
    p1_dist = max(0, distance_on_line - window_deg)
    p2_dist = min(coastline.length, distance_on_line + window_deg)

    p1 = coastline.interpolate(p1_dist)
    p2 = coastline.interpolate(p2_dist)

    # Compute tangent vector
    dx = p2.x - p1.x
    dy = p2.y - p1.y

    # Tangent angle
    tangent_angle = np.degrees(np.arctan2(dy, dx))

    # Normal is perpendicular (add 90 degrees)
    # We want the seaward normal (pointing away from land)
    # Convention: 0° = North, 90° = East
    normal_angle_1 = (tangent_angle + 90) % 360
    normal_angle_2 = (tangent_angle - 90) % 360

    # TODO: Determine which normal points seaward (requires land polygon)
    # For now, return the one pointing more southward (common for west coast)
    shore_normal = normal_angle_1

    return shore_normal


def compute_curvature(
    coastline: LineString, point: Tuple[float, float], window_deg: float = 0.02
) -> float:
    """
    Compute coastline curvature at a point

    Higher curvature = point/reef (concave)
    Lower curvature = beach (straight)

    Args:
        coastline: Coastline as LineString
        point: (lon, lat) point on coastline
        window_deg: Window size for curvature calculation

    Returns:
        Curvature value (1/degrees, positive = seaward bulge)
    """
    lon, lat = point
    p = Point(lon, lat)

    # Find position on line
    distance = coastline.project(p)

    # Get three points: before, at, after
    d1 = max(0, distance - window_deg)
    d2 = distance
    d3 = min(coastline.length, distance + window_deg)

    p1 = coastline.interpolate(d1)
    p2 = coastline.interpolate(d2)
    p3 = coastline.interpolate(d3)

    # Convert to numpy arrays
    coords = np.array([[p1.x, p1.y], [p2.x, p2.y], [p3.x, p3.y]])

    # Compute curvature using three-point method
    # κ = 2 * area / (a * b * c) where a,b,c are side lengths
    a = np.linalg.norm(coords[1] - coords[0])
    b = np.linalg.norm(coords[2] - coords[1])
    c = np.linalg.norm(coords[2] - coords[0])

    # Area of triangle (cross product)
    v1 = coords[1] - coords[0]
    v2 = coords[2] - coords[0]
    area = 0.5 * abs(np.cross(v1, v2))

    # Curvature
    if a * b * c > 0:
        curvature = 2 * area / (a * b * c)
    else:
        curvature = 0.0

    return curvature


def classify_break_type(curvature: float, slope: float) -> str:
    """
    Classify break type based on curvature and slope

    Args:
        curvature: Coastline curvature
        slope: Bathymetric slope

    Returns:
        Break type: "point", "reef", "beach", "unknown"
    """
    if curvature > 0.05 and slope > 0.1:
        return "point"
    elif slope > 0.15:
        return "reef"
    elif curvature < 0.02 and slope < 0.05:
        return "beach"
    else:
        return "unknown"


def generate_candidate_points(
    coastline: LineString, spacing_m: float = 500.0
) -> List[Dict]:
    """
    Generate candidate surf points with shore normals and curvature

    Args:
        coastline: Coastline as LineString (WGS84)
        spacing_m: Spacing between points in meters

    Returns:
        List of candidate point dictionaries with:
        - id: Unique identifier
        - lon, lat: Coordinates
        - shore_normal: Direction in degrees
        - curvature: Curvature value
    """
    # Segment coastline
    points = segment_coastline(coastline, spacing_m)

    # Compute properties for each point
    candidates = []
    for i, (lon, lat) in enumerate(points):
        shore_normal = compute_shore_normal(coastline, (lon, lat))
        curvature = compute_curvature(coastline, (lon, lat))

        candidate = {
            "id": f"cpt_{i:05d}",
            "lon": lon,
            "lat": lat,
            "shore_normal": shore_normal,
            "curvature": curvature,
        }
        candidates.append(candidate)

    logger.info(f"Generated {len(candidates)} candidate points")
    return candidates


def refine_normal_with_land_polygon(
    candidates: List[Dict], land_polygon
) -> List[Dict]:
    """
    Refine shore normals to ensure they point seaward

    Args:
        candidates: List of candidate dictionaries
        land_polygon: Shapely polygon representing land

    Returns:
        Updated candidates with corrected shore normals
    """
    for candidate in candidates:
        lon = candidate["lon"]
        lat = candidate["lat"]
        normal = candidate["shore_normal"]

        # Create test point along normal direction
        normal_rad = np.radians(normal)
        test_distance = 0.01  # ~1 km

        test_lon = lon + test_distance * np.sin(normal_rad)
        test_lat = lat + test_distance * np.cos(normal_rad)
        test_point = Point(test_lon, test_lat)

        # If test point is on land, flip the normal
        if land_polygon.contains(test_point):
            candidate["shore_normal"] = (normal + 180) % 360

    return candidates
