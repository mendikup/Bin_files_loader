from pathlib import Path
from typing import List

import flet as ft

from src.business_logic.models import FlightPoint
from src.gui.state import FlightLogManager
from src.gui.views.home import HomeView
from src.gui.views.map_view import MapView
from src.gui.components.error_dialog import ErrorDialog


class AppManager:
    """
    Central application coordinator: owns managers and handles navigation.

    Responsibilities:
    - Create and hold FlightLogManager (data/state)
    - Perform high-level orchestration: load file, handle errors, navigate between views
    - Keep views thin (views do not fetch data themselves)
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.manager = FlightLogManager()
        # (optional) store a weak ref / callbacks to the current HomeView so we can forward fine-grained UI updates.
        self._home_view_update = None

    def start(self) -> None:
        self.page.on_view_pop = self._handle_view_pop
        self.show_home()

    # --- navigation helpers ----------------------------------------------
    def show_home(self) -> None:
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/",
                controls=[
                    HomeView(page=self.page, on_load_request=self.handle_load_request)
                ],
            )
        )
        self.page.update()

    def show_map(self, points: List[FlightPoint], source_file: Path) -> None:
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/map",
                controls=[
                    MapView(points=points, source_file=source_file)
                ],
            )
        )
        self.page.update()

    def _handle_view_pop(self, event: ft.ViewPopEvent) -> None:
        # simple back behavior: always go to home
        self.show_home()

    # --- orchestration ---------------------------------------------------
    def handle_load_request(self, file_path: Path) -> None:
        """
        Called by HomeView when a user picked a file. This method will:
          - run the blocking load in a background thread
          - forward progress to page via page.call_from_thread
          - on success navigate to the map view with the loaded points
        """
        # schedule the background work
        self.page.run_thread(lambda: self._load_and_show(file_path))

    def _progress_cb(self, count: int) -> None:
        """Progress callback invoked from a background thread. Schedule UI-thread work."""
        # schedule a small UI update or log; HomeView could also register to manager listeners.
        self.page.call_from_thread(lambda: self._on_progress(count))

    def _on_progress(self, count: int) -> None:
        """Runs on the UI thread. Update UI or log progress here."""
        # For now we simply print; later this could update a LoadingIndicator via a registered callback.
        print(f"Progress: {count}")

    def _load_and_show(self, path: Path) -> None:
        try:
            points = self.manager.load_file(path, progress_callback=self._progress_cb)

            # When load completes, schedule navigation on UI thread
            self.page.call_from_thread(lambda: self.show_map(points, path))

        except Exception as e:
            # show error dialog on UI thread
            self.page.call_from_thread(
                lambda: ErrorDialog.show(page=self.page, title="Failed to Load File", message=str(e))
            )
