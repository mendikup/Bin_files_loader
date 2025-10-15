from __future__ import annotations

from pathlib import Path
from business_logic.bin_parser import parse_text_lines

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
