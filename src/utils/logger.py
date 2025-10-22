import logging
from pathlib import Path
from src.utils.config_loader import config


def setup_logger() -> logging.Logger:
    """Create a simple logger using basicConfig and file output."""
    log_dir = Path(__file__).resolve().parents[1] / config.logging.dir
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / config.logging.file_name

    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper(), logging.INFO),
        format=config.logging.format,
        filename=log_file,
        filemode="a"
    )

    console = logging.StreamHandler()
    console.setLevel(logging.ERROR)
    console.setFormatter(logging.Formatter(config.logging.format))
    logging.getLogger().addHandler(console)

    return logging.getLogger("FlightViewer")


logger = setup_logger()
