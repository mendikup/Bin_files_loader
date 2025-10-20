import logging
from pathlib import Path
from typing import Callable, Iterator, Optional

# NOTE:
# - Do NOT fall back to a fake SimpleNamespace for `pymavlink`.
try:
    from pymavlink import mavutil
except ModuleNotFoundError:
    mavutil = None

from src.business_logic.models import FlightPoint

logger = logging.getLogger(__name__)

GPS_NORM_SCALE_FACTOR = 1e7
ALTITUDE_DIVISOR = 100.0
TIMESTAMP_DIVISOR = 1e6
GPS_PROGRESS_REPORT_INTERVAL = 500


def parse_ardupilot_bin(
    path: Path,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Iterator[FlightPoint]:
    """Yield GPS samples from an ArduPilot .BIN flight_log."""
    if not path.exists():
        logger.error(".BIN flight log not found at %s", path)
        raise FileNotFoundError(f"Flight log not found: {path}")

    if mavutil is None:
        logger.error("pymavlink is not installed; cannot parse %s", path)
        raise ModuleNotFoundError(
            "pymavlink is required to parse .BIN ArduPilot logs. "
            "Please install it: pip install pymavlink"
        )

    logger.info("Opening ArduPilot log %s", path)
    log = mavutil.mavlink_connection(str(path))
    count = 0

    try:
        while True:
            try:

                gps_message = flight_log.recv_match(type="GPS", blocking=False)
            except TypeError:
                gps_message = flight_log.recv_match(blocking=False)
                if gps_message and getattr(gps_message, "get_type", lambda: "")() != "GPS":
                    continue
            if message is None:
                logger.debug("No more messages in %s after %d samples", path, count)
                break

            if getattr(gps_message, "I", 1) != 1:
                continue

            count += 1
            if progress_callback and count % GPS_PROGRESS_REPORT_INTERVAL == 0:
                logger.debug(
                    "Processed %d GPS messages from %s", count, path.name
                )
                progress_callback(count)

            lat = gps_message.Lat
            lon = gps_message.Lng

            if abs(lat) > 90:
                lat /= GPS_NORM_SCALE_FACTOR
            if abs(lon) > 180:
                lon /= GPS_NORM_SCALE_FACTOR

            yield FlightPoint(
                lat=lat,
                lon=lon,
                alt=gps_message.Alt / ALTITUDE_DIVISOR,
                ts=gps_message.TimeUS / TIMESTAMP_DIVISOR,
            )
    finally:
        log.close()
        logger.info("Finished parsing %s with %d samples", path.name, count)


def parse_text_csv(path: Path, delimiter: str = ",") -> Iterator[FlightPoint]:
    """Parse a simple CSV file into ``FlightPoint`` objects."""
    if not path.exists():
        logger.error("CSV flight log not found at %s", path)
        raise FileNotFoundError(f"Flight log not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        logger.info("Parsing CSV flight log %s", path)
        for line_num, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [v.strip() for v in line.split(delimiter)]
            if len(parts) < 4:
                logger.error(
                    "Line %d in %s has insufficient columns: %s", line_num, path.name, line
                )
                raise ValueError(
                    f"Line {line_num}: expected at least 4 fields, got {len(parts)}"
                )

            try:
                lat, lon, alt, ts = (float(parts[i]) for i in range(4))
            except ValueError as e:
                logger.error(
                    "Line %d in %s contains invalid numeric data: %s",
                    line_num,
                    path.name,
                    line,
                )
                raise ValueError(f"Line {line_num}: invalid numeric data") from e

            yield FlightPoint(lat=lat, lon=lon, alt=alt, ts=ts)
        logger.info("Completed parsing CSV file %s", path.name)
