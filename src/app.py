import flet as ft

from src.gui.app_manager import AppManager
from src.log_config import setup_logging

APP_TITLE = "Flight Log Viewer"
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700
PAGE_PADDING = 20

def main(page: ft.Page) -> None:
    """Configure the page and start the GUI."""

    setup_logging()

    page.title = APP_TITLE
    page.padding = PAGE_PADDING
    page.window_min_width = WINDOW_MIN_WIDTH
    page.window_min_height = WINDOW_MIN_HEIGHT

    AppManager(page).start_application_lifecycle()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)