"""
FastAPI application for Remote Surf API
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import logging
import os
import numpy as np

from bluebreaks import __version__
from bluebreaks.core.scanner import CoastlineScanner
from bluebreaks.api.tiles import WindTileGenerator, SwellTileGenerator

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Data paths (from environment or defaults)
DATA_DIR = Path(os.getenv("BLUEBREAKS_DATA_DIR", "data"))
GRIB_PATH = DATA_DIR / os.getenv("BLUEBREAKS_GRIB", "")
BATHY_PATH = DATA_DIR / os.getenv("BLUEBREAKS_BATHY", "")
COASTLINE_PATH = DATA_DIR / os.getenv("BLUEBREAKS_COASTLINE", "")

app = FastAPI(
    title="Remote Surf API",
    description="Find unknown surf from a sailboat using oceanographic data",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str


class BBox(BaseModel):
    """Bounding box coordinates"""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """API root - health check"""
    return HealthResponse(status="ok", version=__version__)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(status="ok", version=__version__)


@app.get("/scan")
async def scan(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    time: Optional[str] = Query(None, description="ISO 8601 timestamp"),
    min_score: float = Query(0.0, ge=0.0, le=10.0, description="Minimum score threshold"),
    spacing: float = Query(500.0, ge=100.0, le=2000.0, description="Point spacing in meters"),
) -> JSONResponse:
    """
    Scan a coastline for surf candidates

    Returns GeoJSON FeatureCollection of candidate surf spots with scores.

    Example:
        /scan?bbox=-116,22,-109,28&min_score=5.0&spacing=500
    """
    logger.info(f"Scanning bbox={bbox}, time={time}, min_score={min_score}, spacing={spacing}m")

    # Parse bbox
    try:
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("BBox must have 4 coordinates")
        bbox_tuple = tuple(coords)
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"error": f"Invalid bbox format: {str(e)}"}
        )

    # Parse time
    time_dt = None
    if time:
        try:
            time_dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Invalid time format: {e}, using None")

    # Initialize scanner
    try:
        # Check if data files exist
        grib_path = GRIB_PATH if GRIB_PATH.exists() else None
        bathy_path = BATHY_PATH if BATHY_PATH.exists() else None
        coastline_path = COASTLINE_PATH if COASTLINE_PATH.exists() else None

        scanner = CoastlineScanner(
            grib_path=grib_path,
            bathy_path=bathy_path,
            coastline_path=coastline_path,
        )

        # Run scan
        geojson = scanner.scan(
            bbox=bbox_tuple,
            time=time_dt,
            spacing_m=spacing,
            min_score=min_score,
        )

        scanner.close()

        # Add metadata
        geojson["metadata"] = {
            "bbox": bbox_tuple,
            "time": time,
            "min_score": min_score,
            "spacing_m": spacing,
            "num_candidates": len(geojson["features"]),
            "data_sources": {
                "grib": str(grib_path) if grib_path else "mock",
                "bathymetry": str(bathy_path) if bathy_path else "mock",
                "coastline": str(coastline_path) if coastline_path else "mock",
            },
        }

        return JSONResponse(content=geojson)

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"Scan failed: {str(e)}"}
        )


@app.get("/predict")
async def predict(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    time: Optional[str] = Query(None, description="ISO 8601 timestamp"),
    min_score: float = Query(0.0, ge=0.0, le=10.0, description="Minimum score threshold"),
) -> JSONResponse:
    """
    Enhanced prediction with ML layer

    Returns GeoJSON with final_score = α*physics + (1-α)*ml
    """
    # TODO: Implement ML prediction layer
    logger.info(f"Predicting bbox={bbox}, time={time}, min_score={min_score}")

    return JSONResponse(
        status_code=501, content={"error": "ML prediction not yet implemented"}
    )


@app.get("/layer/wind")
async def wind_layer(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    time: Optional[str] = Query(None, description="ISO 8601 timestamp"),
    spacing: float = Query(0.5, ge=0.1, le=2.0, description="Grid spacing in degrees"),
) -> JSONResponse:
    """
    Wind barb vector tiles (GeoJSON format)

    Returns:
        GeoJSON FeatureCollection with point features containing wind data
    """
    logger.info(f"Generating wind layer: bbox={bbox}, time={time}, spacing={spacing}")

    try:
        # Parse bbox
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("BBox must have 4 coordinates")
        bbox_tuple = tuple(coords)
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"error": f"Invalid bbox format: {str(e)}"}
        )

    # Parse time
    time_dt = None
    if time:
        try:
            time_dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Invalid time format: {e}, using None")

    try:
        # Check if GRIB exists
        grib_path = GRIB_PATH if GRIB_PATH.exists() else None

        # Generate wind tiles
        generator = WindTileGenerator(grib_path)
        generator.load_forecast(time_dt)
        geojson = generator.generate_wind_points(bbox_tuple, spacing, time_dt)

        return JSONResponse(content=geojson)

    except Exception as e:
        logger.error(f"Wind layer generation failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"Wind layer failed: {str(e)}"}
        )


@app.get("/layer/swell/deep")
async def deep_swell_layer(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    time: Optional[str] = Query(None, description="ISO 8601 timestamp"),
    spacing: float = Query(0.5, ge=0.1, le=2.0, description="Grid spacing in degrees"),
) -> JSONResponse:
    """
    Deep-water swell arrow tiles (GeoJSON format)

    Returns:
        GeoJSON FeatureCollection with LineString features for swell arrows
    """
    logger.info(f"Generating swell layer: bbox={bbox}, time={time}, spacing={spacing}")

    try:
        # Parse bbox
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("BBox must have 4 coordinates")
        bbox_tuple = tuple(coords)
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"error": f"Invalid bbox format: {str(e)}"}
        )

    # Parse time
    time_dt = None
    if time:
        try:
            time_dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Invalid time format: {e}, using None")

    try:
        # Check if GRIB exists
        grib_path = GRIB_PATH if GRIB_PATH.exists() else None

        # Generate swell arrows
        generator = SwellTileGenerator(grib_path)
        generator.load_forecast(time_dt)
        geojson = generator.generate_swell_arrows(bbox_tuple, spacing, time_dt)

        return JSONResponse(content=geojson)

    except Exception as e:
        logger.error(f"Swell layer generation failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"Swell layer failed: {str(e)}"}
        )


@app.get("/timeseries")
async def timeseries(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    shore_normal: float = Query(..., description="Shore normal direction (degrees)"),
    depth: float = Query(10.0, description="Depth at location (m)"),
    slope: float = Query(0.05, description="Bottom slope"),
    hours: int = Query(120, ge=24, le=240, description="Forecast hours (default 120 = 5 days)"),
) -> JSONResponse:
    """
    Get 5-day score timeline for a specific location

    Returns hourly scores, tide data, and best 3-hour windows.

    Example:
        /timeseries?lat=25.5&lon=-111.0&shore_normal=270&depth=8&slope=0.05&hours=120
    """
    logger.info(f"Timeseries for lat={lat}, lon={lon}, hours={hours}")

    try:
        from datetime import datetime, timedelta
        from bluebreaks.core.tide import TideModule
        from bluebreaks.core.wave.scoring import calculate_surf_score
        from bluebreaks.core.wave.physics import calculate_exposure, compute_wave_transformation, shoaling_coefficient

        # Initialize tide module
        tide_module = TideModule()

        # Generate time series (hourly)
        start_time = datetime.now()
        times = []
        scores = []
        tide_heights = []
        wave_heights = []

        for hour in range(hours):
            current_time = start_time + timedelta(hours=hour)
            times.append(current_time.isoformat())

            # Mock wave/wind data (would come from GRIB forecast)
            # In production, this would interpolate GRIB data at each time step
            Hs = 2.0 + 0.5 * np.sin(hour * np.pi / 12)  # Varying swell
            Tp = 12.0 + 2.0 * np.cos(hour * np.pi / 24)  # Varying period
            wave_dir = 225.0  # SW swell
            wind_speed = 5.0 + 2.0 * np.sin(hour * np.pi / 6)
            wind_dir = 45.0

            # Get tide
            tide_info = tide_module.get_tide_info(lat, lon, current_time, slope)

            # Calculate exposure and transformation
            exposure = calculate_exposure(wave_dir, shore_normal)
            transform = compute_wave_transformation(wave_dir, shore_normal, depth, Tp)
            shoaling_coeff = shoaling_coefficient(50.0, depth, Tp)

            # Calculate score
            score_result = calculate_surf_score(
                Hs=Hs,
                Tp=Tp,
                wave_dir=wave_dir,
                wind_speed=wind_speed,
                wind_dir=wind_dir,
                shore_normal=shore_normal,
                exposure=exposure,
                refraction_coeff=transform["Kr"],
                shoaling_coeff=shoaling_coeff,
                curvature=0.02,
                slope=slope,
                tide_level=tide_info['height'],
            )

            scores.append(round(score_result['total'], 2))
            tide_heights.append(tide_info['height'])
            wave_heights.append(round(Hs, 1))

        # Find best 3-hour windows
        from bluebreaks.core.tide.tide_module import TideScorer
        scorer = TideScorer()

        # Convert times to datetime objects for window finding
        time_objs = [datetime.fromisoformat(t) for t in times]
        best_windows = scorer.find_best_windows(time_objs, scores, window_hours=3, top_n=5)

        # Format response
        response = {
            "location": {
                "lat": lat,
                "lon": lon,
                "shore_normal": shore_normal,
                "depth_m": depth
            },
            "forecast": {
                "start": times[0],
                "end": times[-1],
                "interval_hours": 1,
                "hours": hours
            },
            "timeseries": {
                "times": times,
                "scores": scores,
                "tide_heights_m": tide_heights,
                "wave_heights_m": wave_heights
            },
            "best_windows": [
                {
                    "start": w['start'].isoformat(),
                    "end": w['end'].isoformat(),
                    "avg_score": w['avg_score'],
                    "peak_score": w['peak_score'],
                    "duration_hours": w['duration_hours']
                }
                for w in best_windows
            ],
            "summary": {
                "avg_score": round(float(np.mean(scores)), 2),
                "max_score": round(float(np.max(scores)), 2),
                "min_score": round(float(np.min(scores)), 2)
            }
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Timeseries failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"Timeseries failed: {str(e)}"}
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
