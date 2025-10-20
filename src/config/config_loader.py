"""Utility helpers for reading application configuration from JSON."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).with_name("config.json")

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    """Return the parsed configuration dictionary."""

    logger.debug("Loading configuration from %s", _CONFIG_PATH)
    with _CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)
    logger.info("Configuration loaded with %d top-level keys", len(config))
    return config


def get_config_value(key: str, default: Any | None = None) -> Any:
    """Fetch a single configuration value, falling back to *default* when absent."""

    if key in load_config():
        logger.debug("Retrieved configuration value for key '%s'", key)
    else:
        logger.warning("Configuration key '%s' missing, returning default", key)
    return load_config().get(key, default)
