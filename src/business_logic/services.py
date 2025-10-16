from pathlib import Path
from typing import List

from src.business_logic.models import FlightPoint
from src.business_logic.bin_parser import parse_ardupilot_bin, parse_text_csv


def load_flight_log(path: Path, progress_callback=None) -> List[FlightPoint]:
    """Load flight log with optional progress reporting."""
    if path.suffix.lower() == ".bin":
        points = list(parse_ardupilot_bin(path, progress_callback))
    else:
        points = list(parse_text_csv(path))
    if not points:
        raise ValueError(f"No flight data found in {path.name}")
    return points


def calculate_center(points: List[FlightPoint]) -> tuple[float, float]:
    """Calculate geographic center of flight path.

    Returns:
        Tuple of (center_lat, center_lon) for map positioning
    """
    if not points:
        return 0.0, 0.0

    avg_lat = sum(p.lat for p in points) / len(points)
    avg_lon = sum(p.lon for p in points) / len(points)

    return avg_lat, avg_lon