"""Utility helpers for reading application configuration from JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).with_name("config.json")

logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Return the parsed configuration dictionary."""

    logger.debug("Loading configuration from %s", _CONFIG_PATH)
    with _CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)
    logger.info("Configuration loaded with %d top-level keys", len(config))
    return config


