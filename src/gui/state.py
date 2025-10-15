"""
Simple global application state.

This module stores state shared between views to keep things simple for learning.
In a larger app, consider a more robust state management strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from drone_flet_basic.src.business_logic.models import FlightPoint


@dataclass
class AppState:
    """Holds user selections and parsed points."""
    selected_file: Optional[Path] = None
    points: List[FlightPoint] = field(default_factory=list)

    def clear(self) -> None:
        """Reset state for a new session."""
        self.selected_file = None
        self.points.clear()


# ✅ A single shared state instance for the app
STATE = AppState()
