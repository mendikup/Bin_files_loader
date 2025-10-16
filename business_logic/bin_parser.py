"""Utilities for turning raw flight logs into :class:`FlightPoint` objects.

Two lightweight parsers are provided:

``parse_ardupilot_bin``
    Reads the binary ``.BIN`` format created by ArduPilot flight controllers.
    The implementation uses :mod:`pymavlink` so that we do not need to re-
    implement MAVLink decoding logic.

``parse_text_lines``
    A tiny helper that understands a CSV-like text representation.  It is
    mostly used in tests and for experimenting with the user interface when a
    binary flight log is not available.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Iterator

try:  # pragma: no cover - exercised indirectly
    from pymavlink import mavutil
except ModuleNotFoundError:  # pragma: no cover - handled in tests
    mavutil = SimpleNamespace()

from business_logic.models import FlightPoint

MINIMUM_FIELDS = 4


def parse_ardupilot_bin(path: Path) -> Iterator[FlightPoint]:
    """Yield :class:`FlightPoint` objects from an ArduPilot ``.BIN`` log file.

    Only ``GPS`` messages are consumed because they contain the location and
    altitude information that we want to draw on the map.  The units reported
    by ArduPilot differ from the ones used in the user interface, therefore the
    parser normalises them before yielding.
    """

    if not path.exists():
        raise FileNotFoundError(f"Flight log not found: {path}")

    if not hasattr(mavutil, "mavlink_connection"):
        raise RuntimeError(
            "pymavlink is required to read ArduPilot BIN logs. "
            "Install it with 'pip install pymavlink'."
        )

    log = mavutil.mavlink_connection(str(path))
    try:
        while True:
            message = log.recv_match(blocking=False)
            if message is None:
                break

            if message.get_type() != "GPS":
                continue

            yield FlightPoint(
                lat=message.Lat / 1e7,
                lon=message.Lng / 1e7,
                alt=message.Alt / 100.0,
                ts=message.TimeUS / 1e6,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
            )
    finally:
        log.close()


def parse_text_lines(path: Path, delimiter: str = ",") -> Iterable[FlightPoint]:
    """Parse a simple comma separated log file into :class:`FlightPoint` objects.

    Parameters
    ----------
    path:
        Path to the file that should be parsed.
    delimiter:
        Character that separates the values in the log.  The default comma works
        well for logs exported from Mission Planner or created manually.

    Yields
    ------
    :class:`FlightPoint`
        One object per valid line in the file.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If a line is missing required fields or contains invalid data.
    """

    if not path.exists():
        raise FileNotFoundError(f"Flight log not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [value.strip() for value in line.split(delimiter)]
            if len(parts) < MINIMUM_FIELDS:
                raise ValueError(
                    "Line "
                    f"{line_number} contains only {len(parts)} fields; "
                    f"expected at least {MINIMUM_FIELDS}."
                )

            try:
                lat, lon, alt, ts = (float(parts[i]) for i in range(4))
                roll = float(parts[4]) if len(parts) > 4 else 0.0
                pitch = float(parts[5]) if len(parts) > 5 else 0.0
                yaw = float(parts[6]) if len(parts) > 6 else 0.0
            except ValueError as exc:  # pragma: no cover - exercised in tests
                raise ValueError(
                    f"Line {line_number} contains invalid numeric data: {line}"
                ) from exc

            yield FlightPoint(
                lat=lat,
                lon=lon,
                alt=alt,
                ts=ts,
                roll=roll,
                pitch=pitch,
                yaw=yaw,
            )
