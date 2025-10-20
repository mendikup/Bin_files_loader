import flet as ft

from config.log_config import setup_logging
from src.gui.app_manager import AppManager


def main(page: ft.Page) -> None:
    """Configure the page and start the GUI."""

    setup_logging()

    page.title = "Flight Log Viewer"
    page.padding = 1000
    page.window_min_width = 700
    page.window_min_height = 20

    AppManager(page).start_application_lifecycle()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)