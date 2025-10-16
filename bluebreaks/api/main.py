"""
FastAPI application for Remote Surf API
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging

from bluebreaks import __version__

logger = logging.getLogger(__name__)

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
) -> JSONResponse:
    """
    Scan a coastline for surf candidates

    Returns GeoJSON FeatureCollection of candidate surf spots with scores.
    """
    # TODO: Implement actual scanning logic
    logger.info(f"Scanning bbox={bbox}, time={time}, min_score={min_score}")

    # Parse bbox
    try:
        coords = [float(x) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("BBox must have 4 coordinates")
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"error": f"Invalid bbox format: {str(e)}"}
        )

    # Mock response
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-111.234, 26.543]},
                "properties": {
                    "id": "cpt_12345",
                    "time": time or "2025-10-18T12:00:00Z",
                    "final_score": 0.82,
                    "physics_score": 0.76,
                    "components": {
                        "expo": 0.88,
                        "refract": 1.10,
                        "wind": 1.06,
                        "tide": 0.96,
                        "period": 1.18,
                        "quality": 1.06,
                    },
                    "swell": {"hs": 2.1, "tp": 15, "dir_deep": 215, "dir_near": 238},
                    "wind": {"spd": 8, "dir": 35, "label": "cross-off"},
                    "tide": {"level_m": 1.2, "label": "mid"},
                    "break_type": "point/reef",
                    "bathy_slope": "steep",
                    "shadowed": False,
                    "anchorage": {
                        "distance_nm": 0.7,
                        "depth_m": 8,
                        "lee_shore_risk": "low",
                        "fetch": "protected S–W",
                    },
                    "remoteness": 0.82,
                    "flags": ["reef nearby", "dinghy landing: moderate"],
                },
            }
        ],
    }

    return JSONResponse(content=geojson)


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
