from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from src.business_logic.models import FlightPoint
from src.business_logic.manager import FlightLogManager
from src.gui.views.home import HomeView
from src.gui.views.map_view import MapView
from src.gui.components.error_dialog import ErrorDialog


class AppManager:
    """
    Central application coordinator: owns the FlightLogManager and handles navigation.
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Manager is now imported from src.business_logic.manager
        self.manager = FlightLogManager()
        self._progress_forwarder: Optional[Callable[[int], None]] = None

    # --- initialization -------------------------------------------------
    def start_application_lifecycle(self) -> None:
        """Initializes the Flet page, sets up navigation, and shows the initial Home view."""
        self.page.on_view_pop = self._handle_view_pop
        self.show_home()

    # --- navigation helpers ---------------------------------------------
    def show_home(self) -> None:
        """Show the Home view."""
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/",
                controls=[
                    HomeView(
                        page=self.page,
                        on_load_request=self.handle_load_request,
                        register_progress_forwarder=self.register_progress_forwarder,
                    )
                ],
            )
        )
        self.page.update()

    def show_map(self, points: List[FlightPoint], source_file: Path) -> None:
        """Show the map view with loaded flight points."""
        self.register_progress_forwarder(None)
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/map",
                controls=[MapView(points=points, source_file=source_file)],
            )
        )
        self.page.update()

    def _handle_view_pop(self, event: ft.ViewPopEvent) -> None:
        """Handles back navigation by returning to the home view."""
        self.show_home()

    # --- orchestration ---------------------------------------------------
    def handle_load_request(self, file_path: Path) -> None:
        """Called by HomeView when a file is picked. Runs load in a background thread."""
        self.page.run_thread(lambda: self._load_and_show(file_path))

    def _load_and_show(self, path: Path) -> None:
        """Loads the flight file on a background thread and handles results."""
        try:
            points = self.manager.load_file(path, progress_callback=self._progress_cb)
            self._schedule_ui(lambda: self._finish_load(points, path))
        except Exception as e:
            self._schedule_ui(lambda: self._handle_load_error(e))

    # --- progress handling -----------------------------------------------
    def _progress_cb(self, count: int) -> None:
        """Called from background thread to report progress. Schedules the UI update."""
        self._schedule_ui(lambda: self._forward_progress(count))

    def _forward_progress(self, count: int) -> None:
        """Updates the progress on the UI thread using the registered forwarder."""
        if self._progress_forwarder:
            try:
                self._progress_forwarder(count)
            except Exception:
                pass
        else:
            print(f"Progress: {count}")

    def register_progress_forwarder(self, fn: Optional[Callable[[int], None]]) -> None:
        """Registers or unregisters a function to receive progress updates."""
        self._progress_forwarder = fn

    # --- load results ----------------------------------------------------
    def _finish_load(self, points: List[FlightPoint], path: Path) -> None:
        """Runs on UI thread when load completes. Navigates to the map view."""
        self.register_progress_forwarder(None)
        self.show_map(points, path)

    def _handle_load_error(self, e: Exception) -> None:
        """Runs on UI thread when load fails. Shows an error dialog."""
        self.register_progress_forwarder(None)
        ErrorDialog.show(
            page=self.page,
            title="Failed to Load File",
            message=str(e),
        )

    # --- UI scheduling utility -------------------------------------------
    def _schedule_ui(self, fn: Callable[[], None]) -> None:
        """
        Safely schedules a callable to run on the main UI thread (thread-safe UI update).
        This is necessary for the background thread to interact with Flet's UI elements.
        It implements multiple fallback methods for Flet version compatibility.
        """
        call = getattr(self.page, "call_from_thread", None)
        if callable(call):
            call(fn)
            return

        invoke = getattr(self.page, "invoke", None)
        if callable(invoke):
            invoke(fn)
            return

        schedule = getattr(self.page, "schedule_task", None)
        if callable(schedule):
            schedule(fn)
            return

        run_async = getattr(self.page, "run_async", None)
        if callable(run_async):
            try:
                run_async(fn)
            except Exception:
                pass
            else:
                return

        try:
            fn()
        except Exception:
            pass