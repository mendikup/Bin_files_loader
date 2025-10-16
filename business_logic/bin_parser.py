"""Utilities for turning raw flight logs into :class:`FlightPoint` objects.

The focus of this project is to make the Flet example as easy to understand
as possible, so the parser intentionally works with a very simple, text-based
format.  Each non-empty line in the input file is expected to contain seven
comma separated values:

```
latitude,longitude,altitude_m,timestamp_s,roll,pitch,yaw
```

If the optional attitude values are missing the parser will default them to
``0.0``.  Lines starting with ``#`` are ignored which makes it possible to add
comments or metadata to log files without breaking the parser.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from business_logic.models import FlightPoint

MINIMUM_FIELDS = 4


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
