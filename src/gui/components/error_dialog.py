from typing import Callable, Optional

import flet as ft


class ErrorDialog:
    """Static helper for showing error dialogs."""

    @staticmethod
    def show(
            page: ft.Page,
            title: str,
            message: str,
            on_retry: Optional[Callable] = None
    ) -> None:
        """Display error dialog with optional retry button.

        Args:
            page: The Flet page to show dialog on
            title: Dialog title text
            message: Error message details
            on_retry: Optional callback for retry button
        """

        def close_dialog(e):
            dialog.open = False
            page.update()

        def handle_retry(e):
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
