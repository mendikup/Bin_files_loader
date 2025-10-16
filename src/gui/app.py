from pathlib import Path
from typing import List

import flet as ft

from src.business_logic.models import FlightPoint
from src.gui.views.home import HomeView
from src.gui.views.map_view import MapView


def main(page: ft.Page) -> None:
    """Initialize and run the Flet application."""

    # Page configuration
    page.title = "Flight Log Viewer"
    page.padding = 20
    page.window_min_width = 1000
    page.window_min_height = 700

    # Navigation: Home screen
    def show_home() -> None:
        page.views.clear()
        page.views.append(
            ft.View(
                route="/",
                controls=[
                    HomeView(
                        page=page,
                        on_loaded=show_map
                    )
                ],
            )
        )
        page.update()

    # Navigation: Map screen
    def show_map(points: List[FlightPoint], source_file: Path) -> None:
        page.views.clear()
        page.views.append(
            ft.View(
                route="/map",
                controls=[
                    MapView(points=points, source_file=source_file)
                ],
            )
        )
        page.update()

    # Back navigation handler
    def handle_view_pop(event: ft.ViewPopEvent) -> None:
        show_home()

    page.on_view_pop = handle_view_pop
    show_home()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)
