from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.business_logic.models import FlightPoint
from src.business_logic.services.file_loader import load_flight_file
from src.business_logic.services.calculations import calculate_center


class FlightLogManager:
    """
    Manages flight log state, progress, and async orchestration.
    Delegates actual loading to the file_loader service.
    """

    def __init__(self) -> None:
        self.points: List[FlightPoint] = []
        self.source_file: Optional[Path] = None
        self.is_loading: bool = False
        self.error: Optional[Exception] = None
        self.last_progress: int = 0
        self._listeners: List[Callable[["FlightLogManager"], None]] = []

    # ---------------------------------------------------------------------
    # Listener management
    # ---------------------------------------------------------------------
    def add_listener(self, fn: Callable[["FlightLogManager"], None]) -> None:
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn: Callable[["FlightLogManager"], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener(self)
            except Exception:
                pass

    # ---------------------------------------------------------------------
    # Progress callback
    # ---------------------------------------------------------------------
    def _internal_progress(self, count: int) -> None:
        self.last_progress = count
        self._notify()

    # ---------------------------------------------------------------------
    # Synchronous load (delegates to service)
    # ---------------------------------------------------------------------
    def load_file(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[FlightPoint]:
        """Delegate actual loading to the file_loader service."""
        self.is_loading = True
        self.error = None
        self.last_progress = 0
        self._notify()

        try:
            points = load_flight_file(path, progress_callback or self._internal_progress)
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
            self._notify()

    # ---------------------------------------------------------------------
    # Async helper returning a Future
    # ---------------------------------------------------------------------
    def load_file_async(
        self,
        path: Path,
        executor: Optional[ThreadPoolExecutor] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Future:
        if executor:
            return executor.submit(self.load_file, path, progress_callback)
        pool = ThreadPoolExecutor(max_workers=1)
        return pool.submit(self.load_file, path, progress_callback)

    # ---------------------------------------------------------------------
    # Convenience
    # ---------------------------------------------------------------------
    def center(self) -> Tuple[float, float]:
        return calculate_center(self.points)
