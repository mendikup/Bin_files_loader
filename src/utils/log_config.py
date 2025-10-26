import logging
import logging.handlers
from pathlib import Path
from src.utils.config_loader import config


def setup_logger() -> logging.Logger:
    """Configure rotating logger that writes to project-root /logs folder."""

    # Always use logs folder in project root
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / config.logging.dir
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / config.logging.file_name


    log_format = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # File handler (rotates when full)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        mode="a",
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))

    # Console handler (only for errors)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.ERROR)

    # Configure the global logger
    logger = logging.getLogger("FlightViewer")
    logger.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    logger.info("Logger configured successfully.")
    return logger


logger = setup_logger()
