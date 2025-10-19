import logging
from pathlib import Path
from typing import Callable, List

from src.business_logic.models import FlightPoint
from src.business_logic.parsers import parse_ardupilot_bin, parse_text_csv

logger = logging.getLogger(__name__)


def load_flight_file(
    path: Path,
    progress_callback: Callable[[int], None] | None = None,
) -> List[FlightPoint]:
    """Load a flight log with the matching parser and ensure it contains data."""
    if path.suffix.lower() == ".bin":
        points = list(parse_ardupilot_bin(path, progress_callback))
    else:
        points = list(parse_text_csv(path))

    if not points:
        raise ValueError(f"No flight data found in {path.name}")

    logger.info("Loaded %d points from %s", len(points), path.name)
    return points