"""Logging helpers for the Elliott Bot application."""

from __future__ import annotations

import logging


def configure_logging(log_level: str) -> None:
    """Configure the root logger for console output."""

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger used across the application."""

    return logging.getLogger(name)
