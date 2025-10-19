"""Utility helpers for reading application configuration from JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).with_name("config.json")


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    """Return the parsed configuration dictionary."""
    with _CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_config_value(key: str, default: Any | None = None) -> Any:
    """Fetch a single configuration value, falling back to *default* when absent."""
    return load_config().get(key, default)
