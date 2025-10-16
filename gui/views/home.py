from __future__ import annotations

from pathlib import Path

import flet as ft

from business_logic.services import load_flight_points
from gui.state import STATE


class HomeView(ft.UserControl):
    """Landing page with a single button to load a flight log."""

    def __init__(self, page: ft.Page, on_done):
        super().__init__()
        self._page = page
        self._on_done = on_done
        self._status = ft.Text("בחר קובץ טיסה בפורמט CSV פשוט")
        self._progress = ft.ProgressRing(visible=False)
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self._page.overlay.append(self._file_picker)

    def build(self) -> ft.Control:
        return ft.Column(
            [
                ft.Text("🚁 מפענח טיסות בסיסי", size=26, weight=ft.FontWeight.BOLD),
                ft.Container(self._status, padding=10),
                self._progress,
                ft.ElevatedButton(
                    "בחר קובץ", icon=ft.icons.UPLOAD_FILE, on_click=self._open_file_picker
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )

    def _open_file_picker(self, _event) -> None:
        self._file_picker.pick_files(allow_multiple=False)

    def _on_file_picked(self, event: ft.FilePickerResultEvent) -> None:
        if not event.files:
            self._status.value = "לא נבחר קובץ"
            self.update()
            return

        path = Path(event.files[0].path)
        self._status.value = f"טוען את {path.name}..."
        self._progress.visible = True
        self.update()

        try:
            STATE.selected_file = path
            STATE.points = load_flight_points(path)
        except Exception as exc:  # pragma: no cover - UI level error handling
            STATE.clear()
            self._status.value = f"❌ שגיאה בקריאת הקובץ: {exc}"
        else:
            self._status.value = f"✅ נטענו {len(STATE.points)} נקודות מסלול"
            self._on_done()
        finally:
            self._progress.visible = False
            self.update()
