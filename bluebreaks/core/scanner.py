"""
Coastline scanner orchestrator

Coordinates all modules to:
1. Load data (GRIB, bathymetry, coastline)
2. Generate candidate points
3. Compute wave physics
4. Calculate scores
5. Return GeoJSON results
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from shapely.geometry import LineString, Point

from bluebreaks.core.data.grib_loader import GRIBLoader
from bluebreaks.core.data.bathy_loader import BathymetryLoader
from bluebreaks.core.data.coastline_loader import CoastlineLoader
from bluebreaks.core.geo.coastline import generate_candidate_points, refine_normal_with_land_polygon
from bluebreaks.core.geo.anchorage import evaluate_anchorage, calculate_remoteness
from bluebreaks.core.wave.physics import (
    calculate_exposure,
    compute_wave_transformation,
    shoaling_coefficient,
)
from bluebreaks.core.wave.scoring import calculate_surf_score
from bluebreaks.core.tide import TideModule

logger = logging.getLogger(__name__)


class CoastlineScanner:
    """Orchestrate scanning of coastline for surf candidates"""

    def __init__(
        self,
        grib_path: Optional[Path] = None,
        bathy_path: Optional[Path] = None,
        coastline_path: Optional[Path] = None,
        tide_stations_path: Optional[Path] = None,
    ):
        """
        Initialize scanner with data sources

        Args:
            grib_path: Path to GRIB forecast file
            bathy_path: Path to bathymetry file
            coastline_path: Path to coastline shapefile/GeoJSON
            tide_stations_path: Path to tide stations JSON file
        """
        self.grib_path = grib_path
        self.bathy_path = bathy_path
        self.coastline_path = coastline_path
        self.tide_stations_path = tide_stations_path

        self.grib_loader: Optional[GRIBLoader] = None
        self.bathy_loader: Optional[BathymetryLoader] = None
        self.coastline_loader: Optional[CoastlineLoader] = None
        self.tide_module: Optional[TideModule] = None

    def scan(
        self,
        bbox: Tuple[float, float, float, float],
        time: Optional[datetime] = None,
        spacing_m: float = 500.0,
        min_score: float = 0.0,
    ) -> Dict:
        """
        Scan coastline for surf candidates

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            time: Forecast time (None = first available)
            spacing_m: Candidate point spacing
            min_score: Minimum score threshold

        Returns:
            GeoJSON FeatureCollection
        """
        logger.info(f"Scanning bbox={bbox}, time={time}, spacing={spacing_m}m")

        # Load data
        wave_data, wind_data = self._load_forecast_data(bbox, time)
        coastline = self._load_coastline(bbox)

        # Generate candidates
        candidates = generate_candidate_points(coastline, spacing_m)
        logger.info(f"Generated {len(candidates)} candidate points")

        # Load bathymetry (if available)
        if self.bathy_path:
            candidates = self._enrich_with_bathymetry(candidates, bbox)

        # Refine shore normals with land polygon
        if self.coastline_loader and self.coastline_loader.land_polygon:
            candidates = refine_normal_with_land_polygon(
                candidates, self.coastline_loader.land_polygon
            )

        # Score candidates
        candidates = self._score_candidates(candidates, wave_data, wind_data, time)

        # Filter by score
        candidates = [c for c in candidates if c.get("score", {}).get("total", 0) >= min_score]
        logger.info(f"Filtered to {len(candidates)} candidates with score >= {min_score}")

        # Convert to GeoJSON
        geojson = self._to_geojson(candidates, time)

        return geojson

    def _load_forecast_data(
        self, bbox: Tuple[float, float, float, float], time: Optional[datetime]
    ) -> Tuple[Dict, Dict]:
        """Load wave and wind forecast data"""
        if not self.grib_path or not Path(self.grib_path).exists():
            logger.warning("No GRIB data - using mock values")
            return self._mock_wave_data(bbox), self._mock_wind_data(bbox)

        try:
            self.grib_loader = GRIBLoader(self.grib_path)
            self.grib_loader.load()

            lon_range = (bbox[0], bbox[2])
            lat_range = (bbox[1], bbox[3])

            wave_data = self.grib_loader.extract_wave_data(lon_range, lat_range, time)
            wind_data = self.grib_loader.extract_wind_data(lon_range, lat_range, time)

            return wave_data, wind_data

        except Exception as e:
            logger.error(f"Failed to load GRIB data: {e}")
            return self._mock_wave_data(bbox), self._mock_wind_data(bbox)

    def _load_coastline(self, bbox: Tuple[float, float, float, float]) -> LineString:
        """Load coastline for bbox"""
        try:
            self.coastline_loader = CoastlineLoader(self.coastline_path)
            self.coastline_loader.load(bbox)
            coastline = self.coastline_loader.extract_coastline(bbox)
            return coastline
        except Exception as e:
            logger.error(f"Failed to load coastline: {e}")
            # Use placeholder
            return self._mock_coastline(bbox)

    def _enrich_with_bathymetry(
        self, candidates: List[Dict], bbox: Tuple[float, float, float, float]
    ) -> List[Dict]:
        """Add bathymetry data to candidates"""
        try:
            self.bathy_loader = BathymetryLoader(self.bathy_path)
            self.bathy_loader.open()

            # Sample depths at candidate locations
            lons = np.array([c["lon"] for c in candidates])
            lats = np.array([c["lat"] for c in candidates])
            depths = self.bathy_loader.sample_depths(lons, lats)

            # Add to candidates
            for i, candidate in enumerate(candidates):
                candidate["depth"] = abs(float(depths[i]))  # Convert to positive meters
                candidate["slope"] = 0.05  # Placeholder - would need local slope calc

        except Exception as e:
            logger.warning(f"Bathymetry enrichment failed: {e}")
            # Add mock depths
            for candidate in candidates:
                candidate["depth"] = 10.0
                candidate["slope"] = 0.05

        return candidates

    def _score_candidates(
        self, candidates: List[Dict], wave_data: Dict, wind_data: Dict, time: Optional[datetime] = None
    ) -> List[Dict]:
        """Score all candidates"""
        # Initialize tide module if not already done
        if not self.tide_module:
            self.tide_module = TideModule(self.tide_stations_path)

        # Use mean values from wave/wind grids (simplified)
        Hs = float(np.nanmean(wave_data.get("hs", 2.0)))
        Tp = float(np.nanmean(wave_data.get("tp", 12.0)))
        wave_dir = float(np.nanmean(wave_data.get("dp", 225.0)))

        wind_speed = float(np.nanmean(wind_data.get("speed", 5.0)))
        wind_dir = float(np.nanmean(wind_data.get("direction", 45.0)))

        # Use current time if not specified
        if time is None:
            time = datetime.now()

        for candidate in candidates:
            shore_normal = candidate["shore_normal"]
            curvature = candidate["curvature"]
            depth = candidate.get("depth", 10.0)
            slope = candidate.get("slope", 0.05)

            # Calculate exposure
            exposure = calculate_exposure(wave_dir, shore_normal)

            # Compute wave transformation (refraction at shore)
            transform = compute_wave_transformation(
                deep_water_dir=wave_dir,
                shore_normal=shore_normal,
                depth_m=depth,
                period_s=Tp
            )
            nearshore_dir = transform["nearshore_direction"]

            # Simple shoaling (would need proper transect)
            shoaling_coeff = shoaling_coefficient(50.0, depth, Tp)
            refraction_coeff = transform["Kr"]

            # Get tide information
            tide_info = self.tide_module.get_tide_info(
                lat=candidate["lat"],
                lon=candidate["lon"],
                time=time,
                slope=slope
            )

            # Calculate score
            score_result = calculate_surf_score(
                Hs=Hs,
                Tp=Tp,
                wave_dir=wave_dir,
                wind_speed=wind_speed,
                wind_dir=wind_dir,
                shore_normal=shore_normal,
                exposure=exposure,
                refraction_coeff=refraction_coeff,
                shoaling_coeff=shoaling_coeff,
                curvature=curvature,
                slope=slope,
                tide_level=tide_info['height'],  # Add tide level for scoring
            )

            candidate["score"] = score_result
            candidate["wave"] = {
                "hs": Hs,
                "tp": Tp,
                "dir": wave_dir,
                "nearshore_dir": nearshore_dir  # Add transformed direction
            }
            candidate["wind"] = {"speed": wind_speed, "dir": wind_dir}
            candidate["tide"] = {
                "height": tide_info['height'],
                "label": tide_info['label'],
                "station": tide_info['station_name']
            }

            # Evaluate anchorage suitability
            land_polygon = self.coastline_loader.land_polygon if self.coastline_loader else None
            anchorage = evaluate_anchorage(
                candidate_lat=candidate["lat"],
                candidate_lon=candidate["lon"],
                candidate_depth=depth,
                wind_dir=wind_dir,
                shore_normal=shore_normal,
                land_polygon=land_polygon
            )
            candidate["anchorage"] = anchorage

            # Calculate remoteness
            remoteness = calculate_remoteness(candidate["lat"], candidate["lon"])
            candidate["remoteness"] = remoteness

        return candidates

    def _to_geojson(self, candidates: List[Dict], time: Optional[datetime]) -> Dict:
        """Convert candidates to GeoJSON FeatureCollection"""
        features = []

        for candidate in candidates:
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [candidate["lon"], candidate["lat"]]},
                "properties": {
                    "id": candidate["id"],
                    "time": time.isoformat() if time else None,
                    "final_score": round(candidate["score"]["total"], 2),
                    "physics_score": round(candidate["score"]["total"], 2),
                    "components": {
                        k: round(v, 2) for k, v in candidate["score"]["components"].items()
                    },
                    "swell": {
                        "hs": round(candidate["wave"]["hs"], 1),
                        "tp": round(candidate["wave"]["tp"], 0),
                        "dir_deep": round(candidate["wave"]["dir"], 0),
                        "dir_nearshore": round(candidate["wave"]["nearshore_dir"], 0),
                    },
                    "wind": {
                        "spd": round(candidate["wind"]["speed"], 1),
                        "dir": round(candidate["wind"]["dir"], 0),
                    },
                    "tide": {
                        "height_m": candidate["tide"]["height"],
                        "label": candidate["tide"]["label"],
                        "station": candidate["tide"]["station"],
                    },
                    "anchorage": {
                        "distance_nm": candidate["anchorage"]["distance_nm"],
                        "depth_m": candidate["anchorage"]["depth_m"],
                        "lee_shore_risk": candidate["anchorage"]["lee_shore_risk"],
                        "fetch": candidate["anchorage"]["fetch"],
                        "dinghy_landing": candidate["anchorage"]["dinghy_landing"],
                    },
                    "remoteness": round(candidate["remoteness"], 2),
                    "flags": candidate["anchorage"]["flags"],
                    "shore_normal": round(candidate["shore_normal"], 1),
                    "curvature": round(candidate["curvature"], 4),
                    "depth_m": round(candidate.get("depth", 10.0), 1),
                    "slope": round(candidate.get("slope", 0.05), 3),
                },
            }
            features.append(feature)

        return {"type": "FeatureCollection", "features": features}

    def _mock_wave_data(self, bbox: Tuple[float, float, float, float]) -> Dict:
        """Generate mock wave data"""
        return {"hs": np.array([[2.1]]), "tp": np.array([[14.0]]), "dp": np.array([[225.0]])}

    def _mock_wind_data(self, bbox: Tuple[float, float, float, float]) -> Dict:
        """Generate mock wind data"""
        return {"speed": np.array([[6.0]]), "direction": np.array([[45.0]])}

    def _mock_coastline(self, bbox: Tuple[float, float, float, float]) -> LineString:
        """Generate mock coastline"""
        min_lon, min_lat, max_lon, max_lat = bbox
        coords = [
            (min_lon + 1, min_lat),
            (min_lon + 1, min_lat + 1),
            (min_lon + 0.8, min_lat + 2),
            (min_lon + 1.2, min_lat + 3),
            (min_lon + 1, max_lat),
        ]
        return LineString(coords)

    def close(self) -> None:
        """Clean up resources"""
        if self.grib_loader:
            self.grib_loader.close()
        if self.bathy_loader:
            self.bathy_loader.close()
        if self.coastline_loader:
            self.coastline_loader.close()
