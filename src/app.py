import flet as ft

from src.gui.app_manager import AppManager


def main(page: ft.Page) -> None:
    """Initialize and run the Flet application."""

    page.title = "Flight Log Viewer"
    page.padding = 20
    page.window_min_width = 1000
    page.window_min_height = 700

    # Create and start the application manager (coordinator)
    app = AppManager(page)
    app.start()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)