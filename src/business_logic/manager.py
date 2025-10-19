from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.business_logic.models import FlightPoint
from src.business_logic.utils.calculate_center import calculate_center, load_flight_file


class FlightLogManager:
    """Store the loaded flight log and expose helper operations."""

    def __init__(self) -> None:
        self.points: List[FlightPoint] = []
        self.source_file: Optional[Path] = None
        self.is_loading: bool = False
        self.error: Optional[Exception] = None
        self.last_progress: int = 0

    def load_file(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[FlightPoint]:
        """Load ``path`` synchronously, update the state, and return the points."""
        self.is_loading = True
        self.error = None
        self.last_progress = 0

        try:
            points = load_flight_file(path, progress_callback)
            self.points = points
            self.source_file = path
            return points
        except Exception as exc:
            self.points = []
            self.source_file = None
            self.error = exc
            raise
        finally:
            self.is_loading = False

    def center(self) -> Tuple[float, float]:
        """Return the geographic center of the cached points."""
        return calculate_center(self.points)
