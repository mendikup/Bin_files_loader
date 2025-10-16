from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, Callable, Optional

try:
    from pymavlink import mavutil
except ModuleNotFoundError:
    mavutil = SimpleNamespace()

from src.business_logic.models import FlightPoint


def parse_ardupilot_bin(
        path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
) -> Iterator[FlightPoint]:
    """
    Parse ArduPilot .BIN file and yield FlightPoint objects.

    Extracts GPS messages and converts units:
    - Lat/Lon: from int (1e7 scale) to decimal degrees
    - Altitude: from centimeters to meters
    - Time: from microseconds to seconds

    Args:
        path: Path to .BIN flight log file
        progress_callback: Optional function to report progress (count)

    Yields:
        FlightPoint objects for each GPS record.
    """
    if not path.exists():
        raise FileNotFoundError(f"Flight log not found: {path}")

    log = mavutil.mavlink_connection(str(path))
    count = 0

    try:
        while True:
            message = log.recv_match(type="GPS", blocking=False)
            if message is None:
                break

            count += 1
            if progress_callback and count % 500 == 0:
                progress_callback(count)

            yield FlightPoint(
                lat=message.Lat / 1e7,
                lon=message.Lng / 1e7,
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
