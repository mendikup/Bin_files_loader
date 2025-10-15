from __future__ import annotations
from pathlib import Path
import flet as ft
import concurrent.futures

from drone_flet_basic.src.business_logic.services import process_bin_file
from drone_flet_basic.src.gui.state import STATE


class HomeView(ft.Container):
    """Home screen: pick a .BIN file and process it synchronously."""

    def __init__(self, on_done):
        super().__init__()
        self.on_done = on_done
        self.status_text = ft.Text("Pick a .BIN file (CSV-like lines)")
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)

        self.content = ft.Column(
            [
                self.file_picker,
                ft.Text("🚁 Drone Flight Viewer — Basic", size=26, weight=ft.FontWeight.BOLD),
                ft.Container(self.status_text, padding=10),
                ft.ElevatedButton(
                    "Load .BIN file",
                    icon=ft.icons.UPLOAD_FILE,
                    on_click=lambda _: self.file_picker.pick_files(allow_multiple=False),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return

        path = Path(e.files[0].path)
        self.status_text.value = f"Loading: {path.name} ..."
        self.update()

        # Run heavy parsing in a background thread
        def parse_file():
            try:
                STATE.selected_file = path
                points = list(process_bin_file(path))
                STATE.points = points
                return f"✅ Done: parsed {len(points)} points."
            except Exception as exc:
                return f"❌ Failed to parse: {exc}"

        def on_finish(future):
            self.status_text.value = future.result()
            self.update()
            self.on_done()  # Now called AFTER thread finishes safely

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(parse_file)
            future.add_done_callback(on_finish)
