import logging
from pathlib import Path
from typing import Callable, Iterator, Optional, List
from pymavlink import mavutil

from src.business_logic.models import FlightPoint

logger = logging.getLogger(__name__)


class FlightLogParser:
    """Parse ArduPilot .BIN flight log files into FlightPoint objects."""

    PROGRESS_UPDATE_INTERVAL = 500
    MIN_VALID_FILE_SIZE = 512  # bytes

    def __init__(self):
        """Initialize parser (no persistent state)."""
        logger.debug("FlightLogParser initialized")

    # ===============================================================
    # Public entry point
    # ===============================================================

    def load_flight_log(self, file_path: Path, on_progress_update: Optional[Callable[[int], None]] = None) -> List[FlightPoint]:
        """Load a .BIN flight log and return parsed GPS points."""
        self._validate_file(file_path)

        logger.info("Loading flight log: %s", file_path.name)
        flight_points = list(self._read_bin_log(file_path, on_progress_update))

        if not flight_points:
            raise ValueError(f"No flight data found in {file_path.name}")

        logger.info("Loaded %d points from %s", len(flight_points), file_path.name)
        return flight_points

    # ===============================================================
    # File validation
    # ===============================================================

    def _validate_file(self, file_path: Path) -> None: #TODO MOVE THE VALIDATION TO THE GUI
        """Ensure file exists, is .BIN, and not empty."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix.lower() != ".bin":
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        file_size = file_path.stat().st_size
        if file_size < self.MIN_VALID_FILE_SIZE:
            raise ValueError(f"File {file_path.name} appears too small ({file_size} bytes)")

    # ===============================================================
    # BIN parsing
    # ===============================================================

    def _read_bin_log(self, file_path: Path, on_progress_update: Optional[Callable[[int], None]] = None) -> Iterator[FlightPoint]:
        """Yield GPS points from an ArduPilot .BIN file."""
        flight_log_data = None
        gps_point_count = 0

        try:
            flight_log_data = mavutil.mavlink_connection(str(file_path))

            for gps_message in iter(lambda: flight_log_data.recv_match(type="GPS", blocking=False), None):
                if getattr(gps_message, "I", 0) != 1:  # Only valid GPS fix
                    continue

                gps_point_count += 1
                if on_progress_update and gps_point_count % self.PROGRESS_UPDATE_INTERVAL == 0:
                    on_progress_update(gps_point_count)

                yield self._convert_to_flight_point(gps_message)

        except Exception as e:
            logger.error("Error reading BIN file %s: %s", file_path.name, e)
            raise

        finally:
            if flight_log_data:
                flight_log_data.close()
            logger.info("Parsed %d GPS points from %s", gps_point_count, file_path.name)

    # ===============================================================
    # Conversion helper
    # ===============================================================

    @staticmethod
    def _convert_to_flight_point(gps_message) -> FlightPoint:
        """Convert MAVLink GPS message to FlightPoint."""
        lat, lon = gps_message.Lat, gps_message.Lng

        # Normalize microdegrees
        if abs(lat) > 90:
            lat /= 1e7
        if abs(lon) > 180:
            lon /= 1e7

        return FlightPoint(
            lat=lat,
            lon=lon,
            alt=gps_message.Alt / 100.0,  # cm → m
            ts=gps_message.TimeUS / 1e6,  # µs → s
        )
