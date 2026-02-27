"""Logging configuration for flat-scraper-bot."""

import logging
import os
from logging.handlers import TimedRotatingFileHandler

_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "scraper.log")


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Logs to both console and a daily-rotating file.  The ``logs/`` directory is
    created automatically if it does not exist.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    os.makedirs(_LOG_DIR, exist_ok=True)

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler — daily rotation, keep 7 backups
    log_file = os.getenv("LOG_FILE", _LOG_FILE)
    os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else _LOG_DIR, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
