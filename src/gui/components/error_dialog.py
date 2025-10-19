from typing import Callable, Optional

import flet as ft


class ErrorDialog:
    """Utility helpers for showing error dialogs."""

    @staticmethod
    def show(
        page: ft.Page,
        title: str,
        message: str,
        on_retry: Optional[Callable] = None,
    ) -> None:
        """Display a modal error message, optionally exposing a retry callback."""

        def close_dialog(_: ft.ControlEvent) -> None:
            dialog.open = False
            page.update()

        def handle_retry(_: ft.ControlEvent) -> None:
            dialog.open = False
            page.update()
            if on_retry:
                on_retry()

        actions = [
            ft.TextButton("Close", on_click=close_dialog),
        ]

        if on_retry:
            actions.insert(0, ft.TextButton("Retry", on_click=handle_retry))

        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=actions,
        )

        page.dialog = dialog
        dialog.open = True
        page.update()