from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.business_logic.models import FlightPoint
from src.business_logic.utils.calculate_center import calculate_center, load_flight_file


class FlightLogManager:
    """Manages flight log data state and delegates file loading.

    This class holds the loaded data and the source file path.
    The internal listener system was removed as it was unused by the AppManager.
    """

    def __init__(self) -> None:
        self.points: List[FlightPoint] = []
        self.source_file: Optional[Path] = None
        self.is_loading: bool = False
        self.error: Optional[Exception] = None
        self.last_progress: int = 0

    # ---------------------------------------------------------------------
    # Synchronous load (delegates to service)
    # ---------------------------------------------------------------------
    def load_file(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[FlightPoint]:
        """Loads a flight file synchronously, updates internal state, and returns the points."""
        self.is_loading = True
        self.error = None
        self.last_progress = 0

        # Note: Internal notification system removed. Relying solely on progress_callback.

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

    # ---------------------------------------------------------------------
    # Convenience
    # ---------------------------------------------------------------------
    def center(self) -> Tuple[float, float]:
        """Calculates the geographic center of the loaded points."""
        return calculate_center(self.points)

# Removed unused method: load_file_async