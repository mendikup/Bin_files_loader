from pathlib import Path
import logging
import logging.config
import sys


def setup_logging() -> None:
    """Configure rotating file and console logging available from anywhere in the project.

    The log directory is always resolved relative to the project root,
    so logs are written correctly no matter where the program is launched from.
    """

    # Project root = one level above the "config" folder
    project_root = Path(__file__).resolve().parents[1]

    # Ensure logs directory exists
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "flight_viewer.log"

    log_format = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"


    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": log_format,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "file_handler": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_file),
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

    # Apply configuration globally
    logging.config.dictConfig(config)
