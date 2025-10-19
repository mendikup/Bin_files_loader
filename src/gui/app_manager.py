from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from src.business_logic.models import FlightPoint
from src.business_logic.manager import FlightLogManager
from src.gui.views.home import HomeView
from src.gui.views.map_view import MapView
from src.gui.components.error_dialog import ErrorDialog


class AppManager:
    """Coordinate navigation, background loading, and progress reporting."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.manager = FlightLogManager()
        self._progress_listener: Optional[Callable[[int], None]] = None

    def start_application_lifecycle(self) -> None:
        """Attach navigation handlers and render the home screen."""
        self.page.on_view_pop = self._handle_view_pop
        self.show_home()

    def show_home(self) -> None:
        """Render the home view."""
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
        self.show_home()

    def handle_load_request(self, file_path: Path) -> None:
        """Start loading the selected file on a worker thread."""
        self.page.run_thread(lambda: self._load_and_show(file_path))

    def _load_and_show(self, path: Path) -> None:
        """Load the file, then switch the UI when done."""
        try:
            points = self.manager.load_file(path, progress_callback=self._progress_cb)
            self._schedule_ui(lambda: self._finish_load(points, path))
        except Exception as e:
            self._schedule_ui(lambda: self._handle_load_error(e))

    def _progress_cb(self, count: int) -> None:
        """Bounce progress updates from the worker thread to the UI thread."""
        self._schedule_ui(lambda: self._forward_progress(count))

    def _forward_progress(self, count: int) -> None:
        """Notify the registered listener or fall back to stdout."""
        if self._progress_listener:
            try:
                self._progress_listener(count)
            except Exception:
                pass
        else:
            print(f"Progress: {count}")

    def set_progress_listener(self, listener: Optional[Callable[[int], None]]) -> None:
        """Register or remove the function that receives progress updates."""
        self._progress_listener = listener

    def _finish_load(self, points: List[FlightPoint], path: Path) -> None:
        """Switch to the map view once data is ready."""
        self.set_progress_listener(None)
        self.show_map(points, path)

    def _handle_load_error(self, e: Exception) -> None:
        """Show an error dialog when the load fails."""
        self.set_progress_listener(None)
        ErrorDialog.show(
            page=self.page,
            title="Failed to Load File",
            message=str(e),
        )

    def _schedule_ui(self, fn: Callable[[], None]) -> None:
        """Run *fn* on the UI thread, falling back to a direct call if needed."""
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