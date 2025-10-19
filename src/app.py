import flet as ft

from src.gui.app_manager import AppManager
# Import configuration constants
from src.config import APP_TITLE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, PAGE_PADDING
# Import the new logging setup function
from src.log_config import setup_logging


def main(page: ft.Page) -> None:
    """Initialize and run the Flet application."""

    # --- 1. SETUP LOGGING ---
    setup_logging()

    page.title = APP_TITLE
    page.padding = PAGE_PADDING
    page.window_min_width = WINDOW_MIN_WIDTH
    page.window_min_height = WINDOW_MIN_HEIGHT

    # Create and start the application manager (coordinator)
    app = AppManager(page)
    app.start_application_lifecycle()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)