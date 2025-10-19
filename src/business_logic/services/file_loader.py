from pathlib import Path
from typing import List, Callable
import logging

from src.business_logic.io.bin_parser import parse_ardupilot_bin, parse_text_csv
from src.business_logic.models import FlightPoint

logger = logging.getLogger(__name__)


def load_flight_file(
    path: Path,
    progress_callback: Callable[[int], None] | None = None
) -> List[FlightPoint]:
    """
    Load flight log (.BIN or .CSV) and return a list of FlightPoint.

    Handles:
    - Determining file type (.bin or .csv)
    - Progress updates via callback
    - Basic validation
    """
    if path.suffix.lower() == ".bin":
        points = list(parse_ardupilot_bin(path, progress_callback))
    else:
        points = list(parse_text_csv(path))

    if not points:
        raise ValueError(f"No flight data found in {path.name}")

    logger.info("Loaded %d points from %s", len(points), path.name)
    return points
