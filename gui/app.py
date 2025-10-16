from __future__ import annotations
import flet as ft

from gui.state import STATE
from gui.views.home import HomeView
from gui.views.map_view import MapView


def main(page: ft.Page) -> None:
    """Configure the application shell and manage navigation."""
    page.title = "מטעין טיסות ב-Flet"
    page.padding = 16
    page.window_min_width = 900
    page.window_min_height = 700
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START

    def show_home() -> None:
        print("[DEBUG] ⏪ חוזרים למסך הבית")
        STATE.clear()
        page.views.clear()
        page.views.append(
            ft.View(
                route="/",
                controls=[HomeView(page=page, on_done=show_map)],
                scroll=ft.ScrollMode.AUTO,
            )
        )
        page.update()

    def show_map() -> None:
        print(f"[DEBUG] 🗺️ מציג מפה עם {len(STATE.points)} נקודות")
        page.views.clear()
        page.views.append(
            ft.View(
                route="/map",
                controls=[MapView()],
                scroll=ft.ScrollMode.AUTO,
            )
        )
        page.update()

    def handle_view_pop(_event: ft.ViewPopEvent) -> None:
        show_home()

    page.on_view_pop = handle_view_pop
    show_home()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)

