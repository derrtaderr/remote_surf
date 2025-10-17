"""
Bathymetry data loader for GEBCO and other depth datasets

Loads and processes bathymetry data for:
- Wave refraction calculations (depth-dependent wave speed)
- Shoaling coefficient computation
- Slope analysis for break type classification
"""

import rasterio
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
from scipy.ndimage import gaussian_filter
import logging

logger = logging.getLogger(__name__)


class BathymetryLoader:
    """Load and process bathymetry raster data (GeoTIFF, NetCDF)"""

    def __init__(self, bathy_path: Path):
        """
        Initialize bathymetry loader

        Args:
            bathy_path: Path to bathymetry file (GeoTIFF, NetCDF)
        """
        self.bathy_path = Path(bathy_path)
        if not self.bathy_path.exists():
            raise FileNotFoundError(f"Bathymetry file not found: {bathy_path}")

        self.src: Optional[rasterio.DatasetReader] = None

    def open(self) -> rasterio.DatasetReader:
        """Open the bathymetry dataset"""
        try:
            self.src = rasterio.open(self.bathy_path)
            logger.info(
                f"Loaded bathymetry: {self.bathy_path} "
                f"({self.src.width}x{self.src.height}, CRS: {self.src.crs})"
            )
            return self.src
        except Exception as e:
            logger.error(f"Failed to load bathymetry: {e}")
            raise

    def sample_depth(self, lon: float, lat: float) -> float:
        """
        Sample depth at a single point

        Args:
            lon: Longitude
            lat: Latitude

        Returns:
            Depth in meters (negative for below sea level, positive for land)
        """
        if self.src is None:
            self.open()

        # Convert lon/lat to pixel coordinates
        row, col = self.src.index(lon, lat)

        # Read value
        try:
            depth = self.src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
            return float(depth)
        except IndexError:
            logger.warning(f"Point ({lon}, {lat}) outside bathymetry bounds")
            return np.nan

    def sample_depths(
        self, lons: np.ndarray, lats: np.ndarray
    ) -> np.ndarray:
        """
        Sample depths at multiple points

        Args:
            lons: Array of longitudes
            lats: Array of latitudes

        Returns:
            Array of depths (same shape as input)
        """
        if self.src is None:
            self.open()

        depths = np.zeros_like(lons, dtype=np.float32)

        for i, (lon, lat) in enumerate(zip(lons.flat, lats.flat)):
            depths.flat[i] = self.sample_depth(lon, lat)

        return depths

    def extract_region(
        self, bbox: Tuple[float, float, float, float], resolution: Optional[float] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract bathymetry for a bounding box

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            resolution: Target resolution in degrees (None = native)

        Returns:
            (depths, lons, lats) arrays
        """
        if self.src is None:
            self.open()

        min_lon, min_lat, max_lon, max_lat = bbox

        # Convert bbox to window
        window = rasterio.windows.from_bounds(
            min_lon, min_lat, max_lon, max_lat, transform=self.src.transform
        )

        # Read data
        depths = self.src.read(1, window=window)

        # Get coordinates
        transform = self.src.window_transform(window)
        height, width = depths.shape

        cols, rows = np.meshgrid(np.arange(width), np.arange(height))
        lons, lats = rasterio.transform.xy(transform, rows, cols)

        lons = np.array(lons)
        lats = np.array(lats)

        # Resample if needed
        if resolution is not None:
            # TODO: Implement resampling
            logger.warning("Resolution resampling not yet implemented")

        return depths, lons, lats

    def compute_slope(
        self, depths: np.ndarray, lons: np.ndarray, lats: np.ndarray, smooth_sigma: float = 1.0
    ) -> np.ndarray:
        """
        Compute bathymetric slope

        Args:
            depths: Depth array
            lons: Longitude array
            lats: Latitude array
            smooth_sigma: Gaussian smoothing sigma (cells)

        Returns:
            Slope array (gradient magnitude in m/m)
        """
        # Smooth depths to reduce noise
        depths_smooth = gaussian_filter(depths, sigma=smooth_sigma)

        # Compute pixel spacing (approximate)
        dx = np.abs(lons[0, 1] - lons[0, 0]) * 111320 * np.cos(np.radians(lats[0, 0]))
        dy = np.abs(lats[1, 0] - lats[0, 0]) * 111320

        # Compute gradients
        dz_dy, dz_dx = np.gradient(depths_smooth, dy, dx)

        # Slope magnitude
        slope = np.sqrt(dz_dx**2 + dz_dy**2)

        return slope

    def classify_slope(self, slope: np.ndarray) -> np.ndarray:
        """
        Classify slope into categories

        Args:
            slope: Slope array (m/m)

        Returns:
            Classification array:
            0 = flat (< 0.01)
            1 = gentle (0.01 - 0.05)
            2 = moderate (0.05 - 0.15)
            3 = steep (> 0.15)
        """
        classification = np.zeros_like(slope, dtype=np.int8)
        classification[slope >= 0.01] = 1
        classification[slope >= 0.05] = 2
        classification[slope >= 0.15] = 3
        return classification

    def get_depth_band(
        self, lons: np.ndarray, lats: np.ndarray, depth_range: Tuple[float, float] = (0, 30)
    ) -> np.ndarray:
        """
        Sample depths within a specific depth range (for wave interaction zone)

        Args:
            lons: Longitude array
            lats: Latitude array
            depth_range: (min_depth, max_depth) in meters (negative values)

        Returns:
            Boolean mask where depths are in range
        """
        depths = self.sample_depths(lons, lats)

        # GEBCO convention: negative = below sea level
        min_depth, max_depth = depth_range
        mask = (depths <= -min_depth) & (depths >= -max_depth)

        return mask

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get dataset bounding box"""
        if self.src is None:
            self.open()

        bounds = self.src.bounds
        return bounds.left, bounds.bottom, bounds.right, bounds.top

    def close(self) -> None:
        """Close the dataset"""
        if self.src is not None:
            self.src.close()
            self.src = None

    def __enter__(self) -> "BathymetryLoader":
        """Context manager entry"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()


def sample_transect(
    bathy_loader: BathymetryLoader,
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
    num_points: int = 100,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Sample bathymetry along a transect (useful for cross-shore profiles)

    Args:
        bathy_loader: BathymetryLoader instance
        start_lon: Starting longitude
        start_lat: Starting latitude
        end_lon: Ending longitude
        end_lat: Ending latitude
        num_points: Number of sample points

    Returns:
        (distances, depths, (lons, lats)) tuple
    """
    lons = np.linspace(start_lon, end_lon, num_points)
    lats = np.linspace(start_lat, end_lat, num_points)

    depths = bathy_loader.sample_depths(lons, lats)

    # Compute distances (approximate)
    dlons = np.diff(lons) * 111320 * np.cos(np.radians(lats[:-1]))
    dlats = np.diff(lats) * 111320
    distances = np.concatenate([[0], np.cumsum(np.sqrt(dlons**2 + dlats**2))])

    return distances, depths, (lons, lats)
