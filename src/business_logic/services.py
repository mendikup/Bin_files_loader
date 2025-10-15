from __future__ import annotations

from pathlib import Path
from typing import List

from drone_flet_basic.src.business_logic.bin_parser import parse_ardupilot_bin
from drone_flet_basic.src.business_logic.models import FlightPoint


def process_bin_file(path: Path) -> List[FlightPoint]:
    """
    Parse a .BIN file synchronously and return a list of FlightPoint objects.
    Raises clear errors for missing or invalid data.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    points = list(parse_ardupilot_bin(path))

    if not points:
        raise ValueError(f"No valid flight points found in {path.name}")

    return points
