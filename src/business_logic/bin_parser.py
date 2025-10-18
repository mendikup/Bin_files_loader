from pathlib import Path
from typing import Callable, Iterator, Optional

# NOTE:
# - Do NOT fall back to a fake SimpleNamespace for `pymavlink`.
# - If pymavlink is not installed we set mavutil = None and raise a clear error
#   at runtime. This avoids confusing AttributeError later when trying to call
#   mavutil.mavlink_connection on a fake object.
try:
    from pymavlink import mavutil
except ModuleNotFoundError:
    mavutil = None

from src.business_logic.models import FlightPoint


def parse_ardupilot_bin(
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
) -> Iterator[FlightPoint]:
    """
    Parse ArduPilot .BIN file and yield FlightPoint objects.

    Changes made:
    - If pymavlink is missing, raise ModuleNotFoundError with a clear message
      instead of silently failing later.
    - Keep the logic otherwise intact (normalization of coordinates, filtering).
    """
    if not path.exists():
        raise FileNotFoundError(f"Flight log not found: {path}")

    if mavutil is None:
        # Clear, actionable message for the user/developer.
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
            if hasattr(message, 'I') and message.I != 0:
                continue

            count += 1
            if progress_callback and count % 500 == 0:
                progress_callback(count)

            lat = message.Lat
            lon = message.Lng

            # Normalize older logs which store lat/lon as int (scale 1e7).
            if abs(lat) > 90:
                lat /= 1e7
            if abs(lon) > 180:
                lon /= 1e7

            yield FlightPoint(
                lat=lat,
                lon=lon,
                alt=message.Alt / 100.0,
                ts=message.TimeUS / 1e6,
            )
    finally:
        log.close()


def parse_text_csv(path: Path, delimiter: str = ",") -> Iterator[FlightPoint]:
    """
    Parse simple CSV text file into FlightPoint objects.

    Expected format per line: lat,lon,alt,timestamp
    Lines starting with # are treated as comments.

    Note:
    - Keeps previous behavior (raises ValueError on malformed numeric fields).
    - Could be extended with a `strict` flag to skip bad lines instead of failing.
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