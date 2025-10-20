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

    logger.debug("Loading flight file %s", path)

    if path.suffix.lower() == ".bin":
        logger.debug("Detected .BIN file, using ArduPilot parser")
        points = list(parse_ardupilot_bin(path, progress_callback))
    else:
        logger.debug("Detected non-.BIN file, using CSV parser")
        points = list(parse_text_csv(path))

    if not points:
        logger.error("No flight data found in %s", path.name)
        raise ValueError(f"No flight data found in {path.name}")

    logger.info("Loaded %d points from %s", len(points), path.name)
    return points
