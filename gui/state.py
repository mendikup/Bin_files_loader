"""Very small state container used by the Flet demo app."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from business_logic.models import FlightPoint


@dataclass
class AppState:
    """Holds the currently selected file and parsed points."""

    selected_file: Optional[Path] = None
    points: List[FlightPoint] = field(default_factory=list)

    def clear(self) -> None:
        """Reset state for a new session."""
        self.selected_file = None
        self.points.clear()


STATE = AppState()
