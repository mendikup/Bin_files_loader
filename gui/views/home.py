from __future__ import annotations
from pathlib import Path
import time

import flet as ft

from business_logic.services import load_flight_points
from gui.state import STATE


class HomeView(ft.Container):
    """Landing page with a single button to load a flight log."""

    def __init__(self, page: ft.Page, on_done):
        super().__init__()
        self._page = page
        self._on_done = on_done
        self._status = ft.Text("בחר קובץ טיסה בפורמט BIN או CSV")
        self._progress = ft.ProgressBar(visible=False, width=400)
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self._page.overlay.append(self._file_picker)

        # מחליף את build() – ב־Flet החדש פשוט מציבים את התוכן ישירות
        self.content = ft.Column(
            [
                ft.Text("🚁 מפענח טיסות בסיסי", size=26, weight=ft.FontWeight.BOLD),
                ft.Container(self._status, padding=10),
                self._progress,
                ft.ElevatedButton(
                    "בחר קובץ", icon=ft.Icons.UPLOAD_FILE, on_click=self._open_file_picker
                )

            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )

    # === פונקציות עזר ===

    def _open_file_picker(self, _event) -> None:
        """פותח את חלון בחירת הקובץ"""
        self._file_picker.pick_files(allow_multiple=False)

    def _on_file_picked(self, event: ft.FilePickerResultEvent) -> None:
        """נטען לאחר בחירת קובץ"""
        if not event.files:
            self._status.value = "לא נבחר קובץ"
            self._page.update()
            return

        path = Path(event.files[0].path)
        self._status.value = f"טוען את {path.name}..."
        self._progress.visible = True
        self._progress.value = 0
        self._page.update()

        try:
            print(f"Loading file: {path}")  # Debug
            STATE.selected_file = path

            # שלב טעינה מדומה
            self._progress.value = 0.3
            self._status.value = f"מפענח {path.name}..."
            self._page.update()

            STATE.points = load_flight_points(path)
            print(f"Loaded {len(STATE.points)} points")  # Debug

            self._progress.value = 1.0
            self._page.update()

            if not STATE.points:
                raise ValueError("לא נמצאו נקודות טיסה בקובץ")

            self._status.value = f"✅ נטענו {len(STATE.points)} נקודות מסלול"
            self._page.update()

            time.sleep(0.5)  # רק כדי להראות את הודעת ההצלחה

            self._on_done()

        except Exception as exc:
            STATE.clear()
            self._status.value = f"❌ שגיאה: {str(exc)}"
            self._progress.visible = False
            self._page.update()
            print(f"Error loading file: {exc}")  # Debug
