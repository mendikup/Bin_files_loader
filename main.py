import flet as ft
from src.gui.app_manager import AppManager


def main(page: ft.Page) -> None:
    """Entry point for the Flet app."""
    app = AppManager(page)
    app.initialize_app()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)