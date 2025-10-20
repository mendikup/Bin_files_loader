import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.business_logic.models import FlightPoint
from src.business_logic.utils.calculate_center import calculate_center
from src.business_logic.utils.file_loader import load_flight_file


logger = logging.getLogger(__name__)


class FlightLogManager:
    """
    Handles loading and storing flight log data.

    This lightweight version focuses purely on data handling
    and delegates all I/O logic to external services.
    """

    def __init__(self) -> None:
        # Flight data
        self.points: List[FlightPoint] = []
        self.source_file: Optional[Path] = None

    def load_file(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[FlightPoint]:
        """
        Loads a flight log synchronously and stores the points.
        Delegates actual reading to the file_loader service.
        """
        try:
            logger.info("Starting to load flight log from %s", path)
            points = load_flight_file(path, progress_callback)
            self.points = points
            self.source_file = path
            logger.info(
                "Successfully loaded %d points from %s", len(points), path.name
            )
            return points
        except Exception:
            # In case of failure, ensure consistent state.
            self.points = []
            self.source_file = None
            logger.exception("Failed to load flight log from %s", path)
            raise

