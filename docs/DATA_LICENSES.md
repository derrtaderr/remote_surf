# Data Sources & Licenses

This document lists all external data sources used by Remote Surf and their licensing requirements.

---

## Required Data Sources

### NOAA WaveWatch III (WW3)
**Description:** Global ocean wave forecasts (significant wave height, period, direction)

**Source:** https://polar.ncep.noaa.gov/waves/

**License:** Public Domain (US Government work)

**Attribution:** Not legally required, but recommended:
> "Wave data from NOAA WaveWatch III model"

**Usage:** GRIB files for swell/wave forecasting

---

### NOAA Global Forecast System (GFS)
**Description:** Global atmospheric forecasts (wind speed, direction, pressure)

**Source:** https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast

**License:** Public Domain (US Government work)

**Attribution:** Recommended:
> "Wind data from NOAA Global Forecast System (GFS)"

**Usage:** GRIB files for wind forecasting

---

### GEBCO Bathymetry
**Description:** General Bathymetric Chart of the Oceans - global ocean depth data

**Source:** https://www.gebco.net/data_and_products/gridded_bathymetry_data/

**License:** GEBCO Grid Terms of Use - Free for research and commercial use with attribution

**Attribution:** **REQUIRED**
> "Bathymetry data from GEBCO Compilation Group (2023) GEBCO_2023 Grid (doi:10.5285/f98b053b-0cbc-6c23-e053-6c86abc0af7b)"

**Usage:** NetCDF/GeoTIFF for wave refraction and shoaling calculations

---

### OpenStreetMap (OSM)
**Description:** Coastline polygons, marinas, ports

**Source:** https://www.openstreetmap.org/

**License:** Open Data Commons Open Database License (ODbL)

**Attribution:** **REQUIRED**
> "Coastline data © OpenStreetMap contributors"

**Terms:**
- Share-alike required for derivative databases
- Attribution required in all uses
- Full license: https://opendatacommons.org/licenses/odbl/

**Usage:** Coastline vectors for segmentation and shadowing tests

---

### Natural Earth
**Description:** Global coastline and administrative boundaries

**Source:** https://www.naturalearthdata.com/

**License:** Public Domain

**Attribution:** Not required, but recommended:
> "Coastline data from Natural Earth"

**Usage:** Fallback coastline data for regions without OSM coverage

---

## Optional Data Sources

### VIIRS Night Lights
**Description:** Nighttime light intensity (remoteness proxy)

**Source:** https://www.ngdc.noaa.gov/eog/viirs.html

**License:** Public Domain (US Government work)

**Attribution:** Recommended:
> "Night light data from NOAA/NASA Suomi NPP VIIRS"

**Usage:** Optional remoteness scoring

---

### NDBC Buoys
**Description:** Real-time and historical buoy observations (wave height, period, direction)

**Source:** https://www.ndbc.noaa.gov/

**License:** Public Domain (US Government work)

**Attribution:** Recommended:
> "Buoy observations from NOAA National Data Buoy Center (NDBC)"

**Usage:** Optional ML training data and observation interpolation

---

### XTide
**Description:** Harmonic tide constituent data

**Source:** https://flaterco.com/xtide/

**License:** GPLv3 (code), various for data (mostly public domain)

**Attribution:** Check specific station data sources

**Usage:** Tide predictions for tide windowing

---

## Attribution Display

### In Application
Display in PWA footer or About section:
```
Data Sources:
• Wave forecasts: NOAA WaveWatch III
• Wind forecasts: NOAA GFS
• Bathymetry: GEBCO 2023
• Coastlines: © OpenStreetMap contributors
```

### In API Responses
Include in API metadata:
```json
{
  "data_sources": {
    "swell": "NOAA WaveWatch III",
    "wind": "NOAA GFS",
    "bathymetry": "GEBCO 2023",
    "coastline": "© OpenStreetMap contributors"
  }
}
```

### In Exports
GeoJSON/GPX exports must include attribution in metadata.

---

## Compliance Checklist

- [ ] GEBCO attribution in UI footer
- [ ] OSM attribution in UI footer + map controls
- [ ] Data sources documented in API /health endpoint
- [ ] Attribution in exported GeoJSON properties
- [ ] Attribution in CLI output when using --verbose
- [ ] Link to this document in main README.md

---

## Updates

This document should be reviewed and updated whenever:
- New data sources are added
- Data source licenses change
- New versions of datasets are used (especially GEBCO)

**Last Updated:** 2025-10-16
