import logging
from typing import List, Tuple
from src.business_logic.models import FlightPoint

logger = logging.getLogger(__name__)


def calculate_center(points: List[FlightPoint]) -> Tuple[float, float]:
    """Calculate geographic center of flight path."""
    if not points:
        return 0.0, 0.0

    avg_lat = sum(p.lat for p in points) / len(points)
    avg_lon = sum(p.lon for p in points) / len(points)

    logger.debug("Center calculated: (%.6f, %.6f)", avg_lat, avg_lon)
    return avg_lat, avg_lon
