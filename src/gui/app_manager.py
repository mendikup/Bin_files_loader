import logging
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from src.business_logic.manager import FlightLogManager
from src.business_logic.models import FlightPoint
from src.gui.components.error_dialog import ErrorDialog
from src.gui.views.home import HomeView
from src.gui.views.map_view import MapView


logger = logging.getLogger(__name__)


class AppManager:
    """Coordinate navigation, background loading, and progress reporting."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.flight_log_manager = FlightLogManager()
        self._progress_listener: Optional[Callable[[int], None]] = None

    def start_application_lifecycle(self) -> None:
        """Attach navigation handlers and render the home screen."""
        logger.info("Starting application lifecycle")
        self.page.on_view_pop = self._handle_view_pop
        self.show_home()

    def show_home(self) -> None:
        """Render the home view."""
        logger.debug("Rendering home view")
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/",
                controls=[
                    HomeView(
                        page=self.page,
                        on_load_request=self.handle_load_request,
                        set_progress_listener=self.set_progress_listener,
                    )
                ],
            )
        )
        self.page.update()

    def show_map(self, points: List[FlightPoint], source_file: Path) -> None:
        """Render the map view for the loaded file."""
        logger.info(
            "Displaying map for %s with %d points", source_file.name, len(points)
        )
        self.set_progress_listener(None)
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/map",
                controls=[MapView(points=points, source_file=source_file)],
            )
        )
        self.page.update()

    def _handle_view_pop(self, event: ft.ViewPopEvent) -> None:
        """Navigate back to the home view when the user closes a route."""
        route = getattr(getattr(event, "view", None), "route", None)
        logger.debug("View pop event received: %s", route)
        self.show_home()

    def handle_load_request(self, file_path: Path) -> None:
        """Start loading the selected file on a worker thread."""
        logger.info("Received request to load file %s", file_path)
        self.page.run_thread(lambda: self._load_and_show(file_path))

    def _load_and_show(self, path: Path) -> None:
        """Load the file, then switch the UI when done."""
        try:
            logger.debug("Background loading started for %s", path)
            points = self.flight_log_manager.load_file(path, progress_callback=self._progress_cb)
            self._schedule_ui(lambda: self._finish_load(points, path))
        except Exception as e:
            logger.exception("Error while loading %s", path)
            self._schedule_ui(lambda: self._handle_load_error(e))

    def _progress_cb(self, count: int) -> None:
        """Bounce progress updates from the worker thread to the UI thread."""
        logger.debug("Progress callback invoked with count=%d", count)
        self._schedule_ui(lambda: self._forward_progress(count))

    def _forward_progress(self, count: int) -> None:
        """Notify the registered listener or fall back to stdout."""
        if self._progress_listener:
            try:
                self._progress_listener(count)
            except Exception:
                logger.exception("Progress listener raised an exception")
        else:
            logger.info("Progress update with no listener: %d", count)

    def set_progress_listener(self, listener: Optional[Callable[[int], None]]) -> None:
        """Register or remove the function that receives progress updates."""
        logger.debug("Setting progress listener: %s", listener)
        self._progress_listener = listener

    def _finish_load(self, points: List[FlightPoint], path: Path) -> None:
        """Switch to the map view once data is ready."""
        logger.info("Finished loading %s; preparing to display map", path.name)
        self.set_progress_listener(None)
        self.show_map(points, path)

    def _handle_load_error(self, e: Exception) -> None:
        """Show an error dialog when the load fails."""
        self.set_progress_listener(None)
        logger.error("Failed to load flight log: %s", e)
        ErrorDialog.show(
            page=self.page,
            title="Failed to Load File",
            message=str(e),
        )

    def _schedule_ui(self, fn: Callable[[], None]) -> None:
        """Run *fn* on the UI thread, falling back to a direct call if needed."""
        call = getattr(self.page, "call_from_thread", None)
        if callable(call):
            logger.debug("Scheduling function via call_from_thread")
            call(fn)
            return

        invoke = getattr(self.page, "invoke", None)
        if callable(invoke):
            logger.debug("Scheduling function via invoke")
            invoke(fn)
            return

        schedule = getattr(self.page, "schedule_task", None)
        if callable(schedule):
            logger.debug("Scheduling function via schedule_task")
            schedule(fn)
            return

        run_async = getattr(self.page, "run_async", None)
        if callable(run_async):
            try:
                logger.debug("Scheduling function via run_async")
                run_async(fn)
            except Exception:
                logger.exception("Failed to schedule function via run_async")
            else:
                return

        try:
            fn()
        except Exception:
            logger.exception("Failed to execute scheduled function directly")
