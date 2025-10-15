from __future__ import annotations

import flet as ft

from drone_flet_basic.src.gui.views.home import HomeView
from drone_flet_basic.src.gui.views.map_view import MapView


def main(page: ft.Page) -> None:
    """App entry point."""
    page.title = "Drone Flight Viewer — Basic"
    page.padding = 16
    page.window_min_width = 900
    page.window_min_height = 700
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START

    def go_to_map() -> None:
        """Navigate to map view after file has been parsed."""
        page.views.clear()
        page.views.append(
            ft.View(route="/map", controls=[MapView()], scroll=ft.ScrollMode.AUTO)
        )
        page.update()

    # first view
    page.views.append(
        ft.View(route="/", controls=[HomeView(on_done=go_to_map)], scroll=ft.ScrollMode.AUTO)
    )
    page.update()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)
