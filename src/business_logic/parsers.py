from pathlib import Path
from typing import Callable, Iterator, Optional

# NOTE:
# - Do NOT fall back to a fake SimpleNamespace for `pymavlink`.
try:
    from pymavlink import mavutil
except ModuleNotFoundError:
    mavutil = None

from src.business_logic.models import FlightPoint
# Import configuration constants
from src.config import (
    GPS_NORM_SCALE_FACTOR,
    ALTITUDE_DIVISOR,
    TIMESTAMP_DIVISOR,
    GPS_PROGRESS_REPORT_INTERVAL,
)


def parse_ardupilot_bin(
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
) -> Iterator[FlightPoint]:
    """Parse ArduPilot .BIN file and yield FlightPoint objects from GPS messages."""
    if not path.exists():
        raise FileNotFoundError(f"Flight log not found: {path}")

    if mavutil is None:
        raise ModuleNotFoundError(
            "pymavlink is required to parse .BIN ArduPilot logs. "
            "Please install it: pip install pymavlink"
        )

    log = mavutil.mavlink_connection(str(path))
    count = 0

    try:
        while True:
            # Use message type filter to get only GPS messages.
            message = log.recv_match(type="GPS", blocking=False)
            if message is None:
                break

            # Filter out non-primary GPS instances when available.
            if getattr(message, 'I') !=1:
                continue

            count += 1
            if progress_callback and count % GPS_PROGRESS_REPORT_INTERVAL == 0:
                progress_callback(count)

            lat = message.Lat
            lon = message.Lng

            # Normalize older logs which store lat/lon as int (scale 1e7).
            if abs(lat) > 90:
                lat /= GPS_NORM_SCALE_FACTOR
            if abs(lon) > 180:
                lon /= GPS_NORM_SCALE_FACTOR

            yield FlightPoint(
                lat=lat,
                lon=lon,
                alt=message.Alt / ALTITUDE_DIVISOR,
                ts=message.TimeUS / TIMESTAMP_DIVISOR,
            )
    finally:
        log.close()


def parse_text_csv(path: Path, delimiter: str = ",") -> Iterator[FlightPoint]:
    """
    Parse simple CSV text file into FlightPoint objects.
    Expected format per line: lat,lon,alt,timestamp.
    """
    if not path.exists():
        raise FileNotFoundError(f"Flight log not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        for line_num, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [v.strip() for v in line.split(delimiter)]
            if len(parts) < 4:
                raise ValueError(
                    f"Line {line_num}: expected at least 4 fields, got {len(parts)}"
                )

            try:
                lat, lon, alt, ts = (float(parts[i]) for i in range(4))
            except ValueError as e:
                raise ValueError(f"Line {line_num}: invalid numeric data") from e

            yield FlightPoint(lat=lat, lon=lon, alt=alt, ts=ts)