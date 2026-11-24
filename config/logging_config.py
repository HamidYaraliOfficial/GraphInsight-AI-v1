"""Logging configuration: console + rotating file in data/logs."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import settings

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("graphinsight")
    if _CONFIGURED:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        settings.ensure_dirs()
        fh = RotatingFileHandler(settings.LOG_DIR / "graphinsight.log",
                                 maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        logger.warning("Could not create the log file; logging to console only.")
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    setup_logging()
    return logging.getLogger("graphinsight" + (f".{name}" if name else ""))
