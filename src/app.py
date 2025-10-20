import logging

import flet as ft

from src.config.log_config import setup_logging
from src.gui.app_manager import AppManager


logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    """Configure the page and start the GUI."""

    setup_logging()
    logger.info("Logger configured, launching Flight Log Viewer UI")

    page.title = "Flight Log Viewer"
    page.padding = 1000
    page.window_min_width = 700
    page.window_min_height = 20

    logger.debug(
        "Page configured: title=%s, padding=%s, min_size=(%s, %s)",
        page.title,
        page.padding,
        page.window_min_width,
        page.window_min_height,
    )

    AppManager(page).start_application_lifecycle()
    logger.info("Application lifecycle started")


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)