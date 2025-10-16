import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, List

import flet as ft

from src.business_logic.models import FlightPoint
from src.business_logic.services import load_flight_log
from src.gui.components.loading_indicator import LoadingIndicator
from src.gui.components.error_dialog import ErrorDialog

class HomeView(ft.Container):
    """Landing page with file picker for loading flight logs."""

    def __init__(
        self,
        page: ft.Page,
        on_loaded: Callable[[List[FlightPoint], Path], None]
    ):
        super().__init__()
        self._page = page
        self._on_loaded = on_loaded
        self._loading = LoadingIndicator()
        self._file_picker = ft.FilePicker(on_result=self._handle_file_picked)
        self._page.overlay.append(self._file_picker)
        self._current_path: Path | None = None

        # UI
        self.content = ft.Column(
            [
                ft.Icon(ft.Icons.FLIGHT, size=80, color=ft.Colors.BLUE),
                ft.Text("Flight Log Viewer", size=32, weight=ft.FontWeight.BOLD),
                ft.Text("Load ArduPilot .BIN or CSV flight logs", size=16, color=ft.Colors.GREY),
                ft.Container(height=20),
                self._loading,
                ft.Container(height=10),
                ft.ElevatedButton(
                    "Select Flight Log",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=lambda _: self._file_picker.pick_files(allow_multiple=False),
                    style=ft.ButtonStyle(padding=20),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
        )

        self.expand = True
        self.alignment = ft.alignment.center

    # -------------------- Events --------------------

    def _handle_file_picked(self, event: ft.FilePickerResultEvent) -> None:
        """Triggered when a file is selected."""
        if not event.files:
            return

        self._current_path = Path(event.files[0].path)
        self._page.run_thread(self._load_file_in_thread)

    def _on_progress(self, count: int) -> None:
        """Called periodically from parser to report progress."""
        self._loading.set_message(f"📡 Loaded {count:,} points...")
        self._page.update()

    def _load_file_in_thread(self) -> None:
        """Load file in a background thread (safe)."""
        if not self._current_path:
            return

        self._loading.show(f"Loading {self._current_path.name}...")
        self._page.update()

        try:
            # Run heavy I/O safely
            with ThreadPoolExecutor() as pool:
                points = pool.submit(
                    load_flight_log, self._current_path, self._on_progress
                ).result()

            self._loading.set_message(f"✅ Loaded {len(points)} points")
            self._page.update()

            import time
            time.sleep(0.6)

            self._on_loaded(points, self._current_path)

        except Exception as e:
            self._loading.hide()
            self._page.update()
            ErrorDialog.show(
                page=self._page,
                title="Failed to Load File",
                message=str(e),
                on_retry=lambda: self._page.run_thread(self._load_file_in_thread),
            )
