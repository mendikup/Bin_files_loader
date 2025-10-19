# src/log_config.py

import logging
import logging.config
import sys

LOG_FILE = "flight_viewer.log"


def setup_logging():
    """
    Sets up the application-wide logging configuration.

    Logs INFO level and above messages to a file and ERROR/CRITICAL to the console (stderr).
    The format includes the file name where the log call was made (filename).
    """

    # 1. Define the format for log messages
    LOG_FORMAT = (
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
    )

    # 2. Define the configuration dictionary
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': LOG_FORMAT,
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'file_handler': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': LOG_FILE,
                'maxBytes': 1024 * 1024 * 5,  # 5 MB
                'backupCount': 5,
            },
            'console_handler': {
                'level': 'ERROR',  # Only show errors and critical issues in the console
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': sys.stderr,
            },
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['file_handler', 'console_handler'],
                'level': 'DEBUG',  # Capture everything internally
                'propagate': True,
            },
        },
    }

    # 3. Apply the configuration
    logging.config.dictConfig(config)