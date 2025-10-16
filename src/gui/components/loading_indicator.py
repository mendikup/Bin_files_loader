import flet as ft


class LoadingIndicator(ft.Container):
    """Shows a spinner with status message during async operations."""

    def __init__(self):
        super().__init__()
        self._message = ft.Text(value="", size=14)
        self._spinner = ft.ProgressRing(width=40, height=40, visible=False)

        # התוכן הראשי של הרכיב
        self.content = ft.Column(
            [self._spinner, self._message],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

        self.alignment = ft.alignment.center

    def show(self, message: str) -> None:
        """Display spinner with given message."""
        self._message.value = message
        self._spinner.visible = True
        self.update()

    def hide(self) -> None:
        """Hide spinner and clear message."""
        self._spinner.visible = False
        self._message.value = ""
        self.update()

    def set_message(self, message: str) -> None:
        """Update message without changing spinner visibility."""
        self._message.value = message
        self.update()
