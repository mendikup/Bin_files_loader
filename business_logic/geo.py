from __future__ import annotations
from typing import Iterable, Tuple
from .models import FlightPoint

def bounds(points: Iterable[FlightPoint]) -> Tuple[float, float, float, float]:
    """Return (min_lat, min_lon, max_lat, max_lon) for given points."""
    min_lat = min(p.lat for p in points)
    max_lat = max(p.lat for p in points)
    min_lon = min(p.lon for p in points)
    max_lon = max(p.lon for p in points)
    return min_lat, min_lon, max_lat, max_lon
