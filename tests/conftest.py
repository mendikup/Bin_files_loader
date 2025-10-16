from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root (which contains the ``business_logic`` package) is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
