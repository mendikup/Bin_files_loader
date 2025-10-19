# src/log_config.py

import logging
import logging.config
import sys

LOG_FILE = "flight_viewer.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"


def setup_logging() -> None:
    """Configure rotating file logging plus an error stream handler."""

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": LOG_FORMAT,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "file_handler": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": LOG_FILE,
                "maxBytes": 1024 * 1024 * 5,
                "backupCount": 5,
            },
            "console_handler": {
                "level": "ERROR",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
            },
        },
        "loggers": {
            "": {
                "handlers": ["file_handler", "console_handler"],
                "level": "DEBUG",
                "propagate": True,
            },
        },
    }

    logging.config.dictConfig(config)
