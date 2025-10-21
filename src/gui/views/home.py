import logging
from pathlib import Path
from typing import Callable
import flet as ft

logger = logging.getLogger(__name__)


class HomeView(ft.Container):
    """Home screen with file picker and progress display."""

    def __init__(self, page: ft.Page, on_load_request: Callable[[Path, Callable[[int], None]], None]):
        """
        Args:
            page: Flet page instance
            on_load_request: Callback function(file_path, progress_callback) to request file loading
        """
        super().__init__()
        self._page = page
        self._on_load_request = on_load_request

        self._file_picker = ft.FilePicker(on_result=self._handle_file_picked)
        self._page.overlay.append(self._file_picker)

        self._create_ui_components()
        self.content = self._build_main_layout()

        # Make the container expand to full height
        self.expand = True

    # ========================================
    # UI Construction
    # ========================================

    def _create_ui_components(self) -> None:
        """Create loading spinner and message text."""
        self._loading_spinner = ft.ProgressRing(width=40, height=40, visible=False)
        self._loading_message = ft.Text(value="", size=14, text_align=ft.TextAlign.CENTER)
        self._loading_section = ft.Column(
            controls=[self._loading_spinner, self._loading_message],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
        )

    def _build_main_layout(self) -> ft.Column:
        """Build the main layout for the home screen."""
        return ft.Column(
            controls=[
                ft.Icon(ft.Icons.FLIGHT, size=80, color=ft.Colors.BLUE),
                ft.Text("Flight Log Viewer", size=32, weight=ft.FontWeight.BOLD),
                ft.Text("Load ArduPilot .BIN or CSV flight logs", size=16, color=ft.Colors.GREY),
                ft.Container(height=20),
                self._loading_section,
                ft.Container(height=10),
                ft.ElevatedButton(
                    text="Select Flight Log",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=self._open_file_picker,
                    style=ft.ButtonStyle(padding=20)
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
            expand=True
        )

    # ========================================
    # UI Actions
    # ========================================

    def _open_file_picker(self, event) -> None:
        """Open the file picker dialog."""
        self._file_picker.pick_files(allow_multiple=False)

    def _show_loading(self, message: str) -> None:
        """Show loading indicator with message."""
        self._loading_message.value = message
        self._loading_spinner.visible = True
        self._page.update()

    def _hide_loading(self) -> None:
        """Hide loading indicator."""
        self._loading_spinner.visible = False
        self._loading_message.value = ""
        self._page.update()

    def _update_progress(self, count: int) -> None:
        """Update progress message with current count."""
        self._loading_message.value = f"📡 Loaded {count:,} points..."
        self._page.update()

    # ========================================
    # Event Handlers
    # ========================================

    def _handle_file_picked(self, event: ft.FilePickerResultEvent) -> None:
        """Handle file selection from picker."""
        if not event.files:
            logger.info("File picker closed without selection")
            return

        file_path: Path = Path(event.files[0].path)
        logger.info("File selected: %s", file_path)

        self._show_loading(f"Loading {file_path.name}...")

        # Pass both the file path AND our progress callback to AppManager
        self._on_load_request(file_path, self._update_progress)