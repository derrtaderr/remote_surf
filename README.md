# Remote Surf (BlueBreaks)

**Find unknown surf spots from your sailboat** — Auto-generate and score surfable breaks along any coastline by fusing oceanographic data: swell, wind, tides, bathymetry, and coastline orientation. Includes anchorage suitability ratings and works fully offline.

[![CI](https://github.com/YOUR_USERNAME/remote_surf/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/remote_surf/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

Remote Surf is a mobile-first Progressive Web App (PWA) + REST API + CLI tool designed for **cruiser-surfers**, delivery skippers, and expedition sailors. Traditional surf forecasting focuses on named, road-accessible breaks. Remote Surf identifies **unnamed, anchor-reachable surf** using physics-based wave transformation models and real-time oceanographic data.

**Core Features:**
- **Auto-generate surf candidates** along any coastline (segmented every 300-600m)
- **Physics-based scoring** (0-10) using wave exposure, refraction, shoaling, wind compatibility, and tide windows
- **Visualize wind & swell arrows** on an interactive map (deep-water + nearshore transformed)
- **Anchorage suitability** with safety flags (lee shore risk, depth, fetch, landing conditions)
- **Best 3-hour windows** for the next 5 days
- **Fully offline-capable** after ingesting GRIB/NetCDF data

---

## Use Cases

1. **Scan a coastline** and get a ranked list of likely surfable breaks
2. **Filter** for offshore winds, period ≥ 12s, safe anchorage depth 3-15m within 1nm
3. **Open spot details** with 5-day timeline, score components, anchorage notes, and risk flags
4. **Import GRIB offline** (email or file) and run full analysis without network

---

## Architecture

```
remote_surf/
├── bluebreaks/           # Python package
│   ├── api/              # FastAPI REST endpoints
│   ├── cli/              # CLI tool (Typer)
│   └── core/
│       ├── data/         # GRIB, bathymetry, coastline loaders
│       ├── geo/          # Coastline segmentation, normals, shadowing
│       ├── wave/         # Wave physics (refraction, shoaling, scoring)
│       ├── tide/         # Tide windowing
│       └── predict/      # ML-based predictive scoring (optional)
├── web/                  # React PWA (MapLibre GL + Workbox)
├── tests/                # Pytest suite
├── notebooks/            # Jupyter analysis notebooks
└── data/                 # Data cache (ignored by git)
```

**Tech Stack:**
- **Backend:** Python 3.11+, FastAPI, xarray, geopandas, shapely, rasterio, pyproj
- **Frontend:** React, Vite, MapLibre GL, Workbox (offline PWA)
- **Data:** GRIB (WW3/GFS), GEBCO bathymetry, OpenStreetMap coastlines
- **ML (optional):** LightGBM/XGBoost for predictive layer

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/remote_surf.git
cd remote_surf
```

**2. Set up Python environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

**3. Set up pre-commit hooks**
```bash
pre-commit install
```

**4. Install frontend dependencies**
```bash
cd web
npm install
cd ..
```

### Running the API

```bash
# Start the FastAPI server
uvicorn bluebreaks.api.main:app --reload --port 8000
```

API will be available at `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- OpenAPI spec: `http://localhost:8000/openapi.json`

### Running the PWA

```bash
cd web
npm run dev
```

PWA will be available at `http://localhost:5173`

### CLI Usage

```bash
# Scan a coastline using GRIB data
bluebreaks scan --grib data/ww3.grb2 --bbox -116,22,-109,28 --out results.geojson

# Rank top spots for a specific time
bluebreaks rank --time 2025-10-18T12:00 --top 50

# Import and cache data
bluebreaks data import --grib data/forecast.grb2 --bathy data/gebco.tif
```

---

## Data Sources

### Required

- **Wind/Swell:** GRIB files (GFS/WW3), Open-Meteo GRIB
- **Bathymetry:** [GEBCO](https://www.gebco.net/) (NetCDF/GeoTIFF)
- **Coastline:** [OpenStreetMap](https://www.openstreetmap.org/) + [Natural Earth](https://www.naturalearthdata.com/)
- **Tides:** XTide harmonic constituents or NOAA/SHOM stations

### Optional

- **Night lights:** VIIRS monthly composites (remoteness proxy)
- **Marinas/ports:** OSM seamark data
- **Buoys:** NDBC/NOAA observations (for ML predictive layer)

**Data Licenses:** See `docs/DATA_LICENSES.md` for attribution and terms.

---

## API Endpoints

### `/scan`
Scan a bounding box and return candidate surf spots with scores.

**Query Parameters:**
- `bbox`: `min_lon,min_lat,max_lon,max_lat`
- `time`: ISO 8601 timestamp (optional, defaults to current)
- `min_score`: Minimum score threshold (0-10)

**Response:** GeoJSON FeatureCollection

### `/predict`
Enhanced scoring with ML predictive layer (optional).

**Query Parameters:** Same as `/scan`

**Response:** GeoJSON with `final_score` combining physics + ML

### `/layer/wind`
Wind barb vector tiles (MVT format).

### `/layer/swell/deep`
Deep-water swell arrow tiles.

### `/timeseries`
5-day score timeline for a specific candidate point.

---

## Wave Physics Model

The core scoring algorithm combines:

```python
SurfScore = Base × Expo^γ × Refract × Wind × Tide × Period × Quality

Where:
  Base       = min(1, Hs_deep / 1.8)           # Wave height normalized
  Expo       = max(0, cos(θ_incident))^1.2     # Exposure to swell
  Refract    = S(h) × R(θ)                     # Shoaling × refraction
  Wind       = f(offshore_angle, speed)        # Offshore winds preferred
  Tide       = g(slope, tide_level)            # Tide window suitability
  Period     = clamp(Tp/10, 0.7, 1.3)          # Long period boost
  Quality    = 0.8-1.2                         # Break type adjustment
```

**Key Physics:**
- **Shadow test:** Great-circle ray tracing to eliminate sheltered points
- **Refraction:** Snell's law with shallow-water wave speed `c ≈ √(g·h)`
- **Shoaling:** Energy concentration as waves approach shore

---

## Development

### Running Tests

```bash
# Python tests
pytest tests/ --cov=bluebreaks

# Frontend tests
cd web
npm run test
```

### Code Quality

```bash
# Lint Python
ruff check .
ruff format .

# Type check
mypy bluebreaks/

# Lint frontend
cd web
npm run lint
```

### Docker

```bash
# Build image
docker build -t remote-surf .

# Run container
docker run -p 8000:8000 -v $(pwd)/data:/app/data remote-surf
```

---

## Roadmap

### MVP (v0.1) - Current Focus
- [x] Repository structure + CI/CD
- [ ] Core data loaders (GRIB, bathymetry, coastline)
- [ ] Wave physics engine (refraction, shoaling, shadowing)
- [ ] SurfScore calculation
- [ ] FastAPI `/scan` endpoint
- [ ] Basic PWA with MapLibre map
- [ ] Wind/swell arrow visualization
- [ ] Offline capabilities (Workbox + IndexedDB)

### v0.2 - Enhanced Features
- [ ] Tide windowing
- [ ] Anchorage suitability scoring
- [ ] Best 3-hour window detection
- [ ] Spot detail drawer with sparklines
- [ ] CLI tool (full functionality)

### v0.3 - Predictive Layer (Optional)
- [ ] Buoy data integration
- [ ] Spatiotemporal interpolation (IDW → kriging)
- [ ] ML-based scoring (LightGBM)
- [ ] `/predict` endpoint with combined physics + ML scores

### v1.0 - Production
- [ ] Multi-region support
- [ ] User-submitted spot validation
- [ ] GPX/MBTiles export
- [ ] Mobile native apps (React Native)

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Code Standards:**
- Python: Follow PEP 8, use type hints, run `ruff` and `mypy`
- JavaScript: Use ESLint + Prettier
- Tests: Maintain >80% coverage
- Commits: Use conventional commit messages

---

## Disclaimer

**NOT FOR NAVIGATION.** This tool provides **heuristic forecasts** for surf exploration only. Always:
- Verify with official nautical charts before anchoring
- Check local regulations and access restrictions
- Assess conditions in person before entering the water
- Never rely solely on automated scoring for safety decisions

Sailor responsibility applies. Use at your own risk.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

**Data Attributions:**
- GEBCO bathymetry: [Attribution required]
- OpenStreetMap: © OpenStreetMap contributors
- NOAA WaveWatch III: Public domain
- See `docs/DATA_LICENSES.md` for complete list

---

## Acknowledgments

Built for the sailing and surfing community. Inspired by countless hours searching for waves from the boat.

Special thanks to:
- NOAA for WaveWatch III data
- GEBCO for global bathymetry
- OpenStreetMap contributors
- The open-source geo/ocean community

---

## Contact

- **Issues:** [GitHub Issues](https://github.com/YOUR_USERNAME/remote_surf/issues)
- **Discussions:** [GitHub Discussions](https://github.com/YOUR_USERNAME/remote_surf/discussions)

**Sail safe, surf better.**
