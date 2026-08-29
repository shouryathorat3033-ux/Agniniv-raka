"""
HEATWATCH Data Ingestion — Logging Configuration
=================================================
Configures structlog for structured JSON logging.
All ingestion pipelines import get_logger() from here.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """
    Configure structlog + standard-library logging.

    Parameters
    ----------
    log_level : str
        One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    log_file : str | None
        Optional path to a log file.
    """

    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout)
    ]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.FileHandler(
                log_file,
                encoding="utf-8"
            )
        )

    logging.basicConfig(
        level=level,
        handlers=handlers,
        format="%(message)s",
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(
                fmt="iso",
                utc=True
            ),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a named structlog logger."""
    return structlog.get_logger(name)