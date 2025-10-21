import logging
from typing import List, Tuple

from src.business_logic.models import FlightPoint

logger = logging.getLogger(__name__)


def calculate_center(points: List[FlightPoint]) -> Tuple[float, float]:
    """Calculate the geographic center (average lat/lon) of the flight path points."""
    if not points:
        return 0.0, 0.0

    avg_lat = sum(p.lat for p in points) / len(points)
    avg_lon = sum(p.lon for p in points) / len(points)

    logger.debug("Center calculated: (%.6f, %.6f)", avg_lat, avg_lon)
    return avg_lat, avg_lon


def convert_to_flight_point (msg) -> FlightPoint:
    """Convert MAVLink GPS message to FlightPoint."""
    lat = msg.Lat
    lon = msg.Lng

    if abs(lat) > 90:  # Normalize microdegrees
        lat /= 1e7
    if abs(lon) > 180:
        lon /= 1e7

    return FlightPoint(lat=lat, lon=lon, alt=msg.Alt / 100.0, ts=msg.TimeUS / 1e6)
