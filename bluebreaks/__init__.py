"""
BlueBreaks - Remote Surf Discovery from Sailboats

Find unknown/remote surf by fusing swell, wind, tides, coastline orientation,
and bathymetry with anchorage suitability scoring.
"""

__version__ = "0.1.0"
__author__ = "Remote Surf Contributors"
__license__ = "MIT"

from bluebreaks.core.geo import coastline
from bluebreaks.core.wave import physics, scoring

__all__ = [
    "__version__",
    "coastline",
    "physics",
    "scoring",
]
