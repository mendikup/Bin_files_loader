"""High level helpers for turning files into flight points."""
from __future__ import annotations

from pathlib import Path
from typing import List

from business_logic.bin_parser import parse_ardupilot_bin, parse_text_lines
from business_logic.models import FlightPoint


def load_flight_points(path: Path) -> List[FlightPoint]:
    """Read the file at ``path`` and return validated :class:`FlightPoint` items."""
    if path.suffix.lower() == ".bin":
        points = list(parse_ardupilot_bin(path))
    else:
        points = list(parse_text_lines(path))
    if not points:
        raise ValueError(f"No flight samples were found in {path.name}")
    return points


# Backwards compatible name used by the GUI module.  Keeping the alias lets us
# gradually rename the function without breaking imports.
process_bin_file = load_flight_points
