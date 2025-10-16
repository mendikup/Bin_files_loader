from __future__ import annotations

from pathlib import Path

from src.business_logic import parse_ardupilot_bin, parse_text_lines


class _DummyMessage:
    def __init__(self, message_type: str, **fields: float) -> None:
        self._message_type = message_type
        for key, value in fields.items():
            setattr(self, key, value)

    def get_type(self) -> str:
        return self._message_type


class _DummyLog:
    def __init__(self, messages: list[_DummyMessage]) -> None:
        self._messages = iter(messages)
        self.closed = False

    def recv_match(self, blocking: bool = False):  # pragma: no cover - exercised
        return next(self._messages, None)

    def close(self) -> None:
        self.closed = True

def test_parse_text_lines_minimal(tmp_path: Path) -> None:
    content = """        32.1,34.8,120.0,1.0,1,2,3
    32.2,34.9,130.0,2.0,1,2,3
    """
    p = tmp_path / "demo.txt"
    p.write_text(content, encoding="utf-8")
    pts = list(parse_text_lines(p))
    assert len(pts) == 2
    assert pts[0].lat == 32.1
    assert pts[0].ts == 1.0


def test_parse_ardupilot_bin(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "flight.bin"
    log_path.write_bytes(b"dummy")

    gps_message = _DummyMessage(
        "GPS",
        Lat=32_100_0000,
        Lng=34_800_0000,
        Alt=12_300,
        TimeUS=2_000_000,
    )
    ignored_message = _DummyMessage("ATT")
    log = _DummyLog([ignored_message, gps_message])

    def fake_connection(path: str):
        assert path == str(log_path)
        return log

    monkeypatch.setattr(
        "business_logic.bin_parser.mavutil.mavlink_connection",
        fake_connection,
        raising=False,
    )

    points = list(parse_ardupilot_bin(log_path))
    assert len(points) == 1
    assert points[0].lat == 32.1
    assert points[0].lon == 34.8
    assert points[0].alt == 123.0
    assert points[0].ts == 2.0
    assert log.closed is True
