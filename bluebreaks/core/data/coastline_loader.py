"""
Coastline data loader for OpenStreetMap and Natural Earth datasets

Loads and processes coastline polygons for:
- Candidate point generation
- Shadowing calculations (land blocking)
- Shore normal computation
"""

import geopandas as gpd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Union
from shapely.geometry import LineString, Polygon, MultiPolygon, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
import logging

logger = logging.getLogger(__name__)


class CoastlineLoader:
    """Load and process coastline vector data"""

    def __init__(self, coastline_path: Optional[Path] = None):
        """
        Initialize coastline loader

        Args:
            coastline_path: Path to coastline shapefile/GeoJSON (optional, can use OSM)
        """
        self.coastline_path = coastline_path
        self.gdf: Optional[gpd.GeoDataFrame] = None
        self.land_polygon: Optional[Union[Polygon, MultiPolygon]] = None
        self.spatial_index: Optional[STRtree] = None

    def load(self, bbox: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """
        Load coastline data

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat) to filter

        Returns:
            GeoDataFrame with coastline geometries
        """
        if self.coastline_path and Path(self.coastline_path).exists():
            # Load from file
            try:
                self.gdf = gpd.read_file(self.coastline_path)
                logger.info(f"Loaded coastline from {self.coastline_path}: {len(self.gdf)} features")
            except Exception as e:
                logger.error(f"Failed to load coastline: {e}")
                raise
        else:
            # TODO: Fetch from OSM Overpass API
            logger.warning("OSM fetching not yet implemented - using placeholder")
            self.gdf = self._create_placeholder_coastline(bbox)

        # Filter by bbox if provided
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            self.gdf = self.gdf.cx[min_lon:max_lon, min_lat:max_lat]

        # Ensure CRS is WGS84
        if self.gdf.crs is None:
            self.gdf.set_crs("EPSG:4326", inplace=True)
        elif self.gdf.crs != "EPSG:4326":
            self.gdf = self.gdf.to_crs("EPSG:4326")

        # Create unified land polygon for shadowing
        self._create_land_polygon()

        return self.gdf

    def _create_placeholder_coastline(
        self, bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> gpd.GeoDataFrame:
        """Create a simple placeholder coastline for testing"""
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
        else:
            # Default: Baja California region
            min_lon, min_lat, max_lon, max_lat = -116, 22, -109, 28

        # Create a simple coastline (west side of bbox)
        coords = [
            (min_lon + 1, min_lat),
            (min_lon + 1, min_lat + 2),
            (min_lon + 0.5, min_lat + 3),
            (min_lon + 1.5, min_lat + 4),
            (min_lon + 1, max_lat),
        ]

        line = LineString(coords)
        gdf = gpd.GeoDataFrame({"geometry": [line]}, crs="EPSG:4326")

        logger.info("Created placeholder coastline for testing")
        return gdf

    def _create_land_polygon(self) -> None:
        """Create unified land polygon from coastline features"""
        try:
            # Extract polygon geometries
            polygons = []
            for geom in self.gdf.geometry:
                if isinstance(geom, Polygon):
                    polygons.append(geom)
                elif isinstance(geom, MultiPolygon):
                    polygons.extend(geom.geoms)
                elif isinstance(geom, LineString):
                    # Create a buffer around lines to make polygons
                    polygons.append(geom.buffer(0.01))

            if polygons:
                self.land_polygon = unary_union(polygons)
                logger.info(f"Created land polygon from {len(polygons)} features")
            else:
                logger.warning("No polygons found for land mask")

            # Create spatial index
            if polygons:
                self.spatial_index = STRtree(polygons)

        except Exception as e:
            logger.error(f"Failed to create land polygon: {e}")

    def extract_coastline(
        self, bbox: Tuple[float, float, float, float], simplify_tolerance: float = 0.001
    ) -> LineString:
        """
        Extract coastline as LineString for a bounding box

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            simplify_tolerance: Simplification tolerance in degrees

        Returns:
            Merged coastline as LineString
        """
        if self.gdf is None:
            self.load(bbox)

        min_lon, min_lat, max_lon, max_lat = bbox
        subset = self.gdf.cx[min_lon:max_lon, min_lat:max_lat]

        # Extract boundaries
        lines = []
        for geom in subset.geometry:
            if isinstance(geom, Polygon):
                lines.append(geom.boundary)
            elif isinstance(geom, MultiPolygon):
                for poly in geom.geoms:
                    lines.append(poly.boundary)
            elif isinstance(geom, LineString):
                lines.append(geom)

        if not lines:
            logger.warning("No coastline found in bbox")
            return LineString()

        # Merge lines
        merged = unary_union(lines)

        # Simplify
        if simplify_tolerance > 0:
            merged = merged.simplify(simplify_tolerance, preserve_topology=True)

        return merged

    def is_land(self, lon: float, lat: float) -> bool:
        """
        Check if a point is on land

        Args:
            lon: Longitude
            lat: Latitude

        Returns:
            True if point is on land
        """
        if self.land_polygon is None:
            logger.warning("Land polygon not created, cannot check land intersection")
            return False

        point = Point(lon, lat)
        return self.land_polygon.contains(point)

    def is_shadowed(self, point: Point, swell_direction: float, max_distance: float = 50.0) -> bool:
        """
        Check if a point is shadowed by land from a swell direction

        Args:
            point: Point to check
            swell_direction: Swell direction in degrees (oceanographic: direction FROM)
            max_distance: Maximum ray distance in km

        Returns:
            True if shadowed by land
        """
        if self.land_polygon is None:
            return False

        # Convert direction to radians (coming FROM, so reverse)
        angle_rad = np.radians((swell_direction + 180) % 360)

        # Create ray from point in swell direction
        # 1 degree ≈ 111 km
        ray_length_deg = max_distance / 111.0

        end_lon = point.x + ray_length_deg * np.sin(angle_rad)
        end_lat = point.y + ray_length_deg * np.cos(angle_rad)

        ray = LineString([(point.x, point.y), (end_lon, end_lat)])

        # Check intersection with land
        return ray.intersects(self.land_polygon)

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get coastline bounding box"""
        if self.gdf is None:
            raise ValueError("Coastline not loaded")

        bounds = self.gdf.total_bounds
        return tuple(bounds)

    def close(self) -> None:
        """Clean up resources"""
        self.gdf = None
        self.land_polygon = None
        self.spatial_index = None

    def __enter__(self) -> "CoastlineLoader":
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()


def fetch_osm_coastline(bbox: Tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """
    Fetch coastline from OpenStreetMap Overpass API

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat)

    Returns:
        GeoDataFrame with coastline features

    Note: This is a placeholder - full implementation requires overpy or similar
    """
    # TODO: Implement OSM Overpass query
    # Example query:
    # [bbox:{min_lat},{min_lon},{max_lat},{max_lon}];
    # (
    #   way["natural"="coastline"];
    #   relation["natural"="coastline"];
    # );
    # out geom;

    logger.warning("OSM fetching not implemented - use CoastlineLoader with local file")
    raise NotImplementedError("OSM fetching requires overpy library")
