import logging
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from config.log_config import setup_logging
from src.business_logic.flight_log_parser import FlightLogParser
from src.business_logic.models import FlightPoint
from src.gui.error_handler import ErrorDialog
from src.gui.views.home import HomeView
from src.gui.views.map_view import MapView

logger = logging.getLogger(__name__)


class AppManager:
    """
    Manages application lifecycle and coordinates components.
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.flight_log_manager = FlightLogParser()

    # ========================================
    # Initialization
    # ========================================

    def initialize_app(self) -> None:
        """Configure logging, page settings, and start the app."""
        self._configure_logging()
        self._configure_page()
        self._start_lifecycle()

    def _configure_logging(self) -> None:
        """Set up logging system."""
        setup_logging()
        logger.info("Logger configured successfully.")

    def _configure_page(self) -> None:
        """Configure page appearance and constraints."""
        self.page.title = "Flight Log Viewer"
        self.page.padding = 20
        self.page.window_min_width = 700
        self.page.window_min_height = 400
        logger.debug("Page configured: %s", self.page.title)

    def _start_lifecycle(self) -> None:
        """Attach navigation handlers and show home screen."""
        logger.info("Starting application lifecycle")
        self.page.on_view_pop = self._on_view_pop
        self.show_home()

    # ========================================
    # Navigation
    # ========================================

    def _on_view_pop(self, event: ft.ViewPopEvent) -> None:
        """Handle back navigation - returns to home screen."""
        current_route: Optional[str] = getattr(getattr(event, "view", None), "route", None)
        logger.debug("View pop event from route: %s", current_route)
        self.show_home()

    def show_home(self) -> None:
        """Display home screen with file picker."""
        logger.debug("Showing home view")
        self.page.views.clear()

        home_view: HomeView = HomeView(page=self.page, on_load_request=self.handle_load_request)

        self.page.views.append(ft.View(route="/", controls=[home_view]))
        self.page.update()

    def show_map(self, points: List[FlightPoint], source_file: Path) -> None:
        """Display map view with loaded flight data."""
        logger.info("Showing map: %s with %d points", source_file.name, len(points))
        self.page.views.clear()

        map_view: MapView = MapView(points=points, source_file=source_file)

        self.page.views.append(ft.View(route="/map", controls=[map_view]))
        self.page.update()

    # ========================================
    # File Operations
    # ========================================

    def handle_load_request(self, file_path: Path, ui_progress_callback: Callable[[int], None]) -> None:
        """
        Start loading selected file in background thread.
        """
        logger.info("Loading file: %s", file_path)
        self.page.run_thread(lambda: self._load_file_background(file_path, ui_progress_callback))

    def _load_file_background(self, file_path: Path, ui_progress_callback: Callable[[int], None]) -> None:
        """
        Load file on worker thread and handle results.
        Runs in background - does not block UI thread.
        """
        try:
            logger.debug("Background loading: %s", file_path)

            # Load file with progress tracking
            loaded_points: List[FlightPoint] = self.flight_log_manager.load_flight_log(
                file_path,
                on_progress_update=lambda point_count: self._forward_progress_to_ui(point_count, ui_progress_callback)
            )

            # Schedule success handler on UI thread
            self._run_on_ui_thread(lambda: self._on_load_success(loaded_points, file_path))

        except Exception as error:
            logger.error("Load error for %s: %s", file_path, error)
            # Schedule error handler on UI thread
            self._run_on_ui_thread(lambda: self._on_load_error(error))

    def _on_load_success(self, points: List[FlightPoint], path: Path) -> None:
        """Handle successful file load (runs on UI thread)."""
        logger.info("Load complete: %s with %d points", path.name, len(points))
        self.show_map(points, path)

    def _on_load_error(self, error: Exception) -> None:
        """Handle file load failure (runs on UI thread)."""
        logger.error("Load failed: %s", error)
        ErrorDialog.show(page=self.page, title="Failed to Load File", message=str(error))

    # ========================================
    # Progress Handling
    # ========================================

    def _forward_progress_to_ui(self, point_count: int, ui_callback: Callable[[int], None]) -> None:
        """
        Forward progress update from worker thread to UI thread.

        Args:
            point_count: Number of GPS points loaded so far
            ui_callback: UI callback function to update display
        """
        logger.debug("Progress update: %d points", point_count)
        self._run_on_ui_thread(lambda: ui_callback(point_count))

    # ========================================
    # Threading Utilities
    # ========================================

    def _run_on_ui_thread(self, ui_function: Callable[[], None]) -> None:
        """
        Execute function safely on UI thread.
        """
        try:
            ui_function()
        except Exception as error:
            logger.error("UI thread execution failed: %s", error)