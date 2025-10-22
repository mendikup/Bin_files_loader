import flet as ft
from pathlib import Path
from typing import Callable, List

from src.utils.logger import logger
from src.utils.config_loader import config
from src.business_logic.flight_log_parser import FlightLogParser
from src.business_logic.models import FlightPoint
from src.gui.error_handler import ErrorDialog
from src.gui.views.home_view import HomeView
from src.gui.views.map_view import MapView


class AppManager:
    """Manages application lifecycle and coordinates components."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.flight_log_parser = FlightLogParser()

    def initialize_app(self) -> None:
        logger.info("Initializing Flight Log Viewer...")
        self._configure_page()
        self._start_lifecycle()

    def _configure_page(self) -> None:
        self.page.title = config.app.title
        self.page.padding = config.app.padding
        self.page.window_min_width = config.app.min_width
        self.page.window_min_height = config.app.min_height
        logger.debug(f"Configured page: {self.page.title}")

    def _start_lifecycle(self) -> None:
        logger.info("Starting application lifecycle")
        self.page.on_view_pop = self._on_view_pop
        self.show_home()

    def _on_view_pop(self, _: ft.ViewPopEvent) -> None:
        logger.debug("Navigating back to home view")
        self.show_home()

    def show_home(self) -> None:
        self.page.views.clear()
        home_view = HomeView(page=self.page, on_load_request=self.handle_load_request)
        self.page.views.append(ft.View(route="/", controls=[home_view]))
        self.page.update()

    def show_map(self, points: List[FlightPoint], source_file: Path) -> None:
        logger.info(f"Displaying map for {source_file.name} ({len(points)} points)")
        self.page.views.clear()
        map_view = MapView(points=points, source_file=source_file)
        self.page.views.append(ft.View(route="/map", controls=[map_view]))
        self.page.update()

    def handle_load_request(self, file_path: Path, ui_progress_callback: Callable[[int], None]) -> None:
        logger.info(f"Loading file: {file_path}")
        self.page.run_thread(lambda: self._load_file_background(file_path, ui_progress_callback))

    def _load_file_background(self, file_path: Path, ui_progress_callback: Callable[[int], None]) -> None:
        try:
            points = self.flight_log_parser.load_flight_log(
                file_path,
                on_progress_update=lambda count: self._forward_progress_to_ui(count, ui_progress_callback),
            )
            self._run_on_ui_thread(lambda: self._on_load_success(points, file_path))
        except Exception as error:
            logger.error(f"Error loading file {file_path}: {error}")
            self._run_on_ui_thread(lambda: self._on_load_error(error))

    def _on_load_success(self, points: List[FlightPoint], path: Path) -> None:
        logger.info(f"Loaded {len(points)} points from {path.name}")
        self.show_map(points, path)

    def _on_load_error(self, error: Exception) -> None:
        logger.error(f"Load failed: {error}")
        ErrorDialog.show(page=self.page, title="Failed to Load File", message=str(error))

    def _forward_progress_to_ui(self, point_count: int, ui_callback: Callable[[int], None]) -> None:
        logger.debug(f"Progress update: {point_count} points")
        self._run_on_ui_thread(lambda: ui_callback(point_count))

    def _run_on_ui_thread(self, ui_function: Callable[[], None]) -> None:
        try:
            ui_function()
        except Exception as error:
            logger.error(f"Error executing function on UI thread: {error}")
