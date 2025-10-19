from pathlib import Path
from typing import Callable, Optional

import flet as ft

from src.gui.components.loading_indicator import LoadingIndicator


class HomeView(ft.Container):
    """Home screen with a file picker and progress feedback."""

    def __init__(
        self,
        page: ft.Page,
        on_load_request: Callable[[Path], None],
        set_progress_listener: Optional[Callable[[Optional[Callable[[int], None]]], None]] = None,
    ):
        super().__init__()
        self._page = page
        self._on_load_request = on_load_request
        self._set_progress_listener = set_progress_listener
        self._loading = LoadingIndicator()
        self._file_picker = ft.FilePicker(on_result=self._handle_file_picked)
        self._page.overlay.append(self._file_picker)

        if self._set_progress_listener:
            self._set_progress_listener(self._on_progress)

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

    def _handle_file_picked(self, event: ft.FilePickerResultEvent) -> None:
        """Handle a successful pick by showing progress and delegating the load."""
        if not event.files:
            return

        file_path = Path(event.files[0].path)
        self._loading.show(f"Loading {file_path.name}...")
        self._page.update()

        self._on_load_request(file_path)

    def _on_progress(self, count: int) -> None:
        """Update the loading message from UI-thread callbacks."""
        self._loading.set_message(f"📡 Loaded {count:,} points...")
        self._page.update()