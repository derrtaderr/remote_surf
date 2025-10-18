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

from bluebreaks import __version__
from bluebreaks.core.scanner import CoastlineScanner

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
    time: Optional[str] = Query(None, description="ISO 8601 timestamp"),
    format: str = Query("mvt", description="Output format (mvt, geojson)"),
) -> JSONResponse:
    """Wind barb vector tiles"""
    # TODO: Implement wind barb tiler
    return JSONResponse(status_code=501, content={"error": "Not yet implemented"})


@app.get("/layer/swell/deep")
async def deep_swell_layer(
    time: Optional[str] = Query(None, description="ISO 8601 timestamp"),
    format: str = Query("mvt", description="Output format (mvt, geojson)"),
) -> JSONResponse:
    """Deep-water swell arrow tiles"""
    # TODO: Implement swell arrow tiler
    return JSONResponse(status_code=501, content={"error": "Not yet implemented"})


@app.get("/timeseries")
async def timeseries(
    point_id: str = Query(..., description="Candidate point ID"),
) -> JSONResponse:
    """5-day score timeline for a specific point"""
    # TODO: Implement timeseries endpoint
    return JSONResponse(status_code=501, content={"error": "Not yet implemented"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
