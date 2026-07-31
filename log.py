"""
NHPC Weather Warning System — Structured Logging Utilities.

Provides a single ``setup_logging()`` entry point that configures the
root logger for the entire application. Supports two output formats:

- **text** (default, development): Colored console output via colorlog.
- **json** (production): Structured JSON lines via python-json-logger,
  suitable for ELK, CloudWatch, Datadog, or any log aggregator.

Optional file-based log rotation is available when LOG_FILE is set.

Usage:
    from log import setup_logging, get_logger
    setup_logging()  # Call once at startup
    logger = get_logger(__name__)
    logger.info("Server started", extra={"port": 8000})
"""

import logging
import logging.handlers
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    fmt: str = "text",
    log_file: str = "",
) -> None:
    """Configure the root logger for the entire application.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        fmt: Output format — 'text' for colored console, 'json' for
             structured JSON lines.
        log_file: Optional file path for log rotation. Empty string
                  means stdout-only.
    """
    root = logging.getLogger()

    # Prevent duplicate handlers on repeated calls
    root.handlers.clear()

    log_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(log_level)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if fmt == "json":
        console_handler.setFormatter(_get_json_formatter())
    else:
        console_handler.setFormatter(_get_colored_formatter())

    root.addHandler(console_handler)

    # --- Optional file handler with rotation ---
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        # Always use plain text for file logs (JSON is for console/aggregator)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Thin wrapper over ``logging.getLogger`` for consistency.
    All loggers inherit the root configuration set by ``setup_logging()``.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.
    """
    return logging.getLogger(name)


# -----------------------------------------------------------------------
# Private helpers
# -----------------------------------------------------------------------

def _get_json_formatter() -> logging.Formatter:
    """Return a JSON formatter for structured log output.

    Uses python-json-logger if available; falls back to a minimal
    JSON formatter if the package is not installed.
    """
    try:
        from pythonjsonlogger import jsonlogger

        return jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
        )
    except ImportError:
        # Fallback: plain text with a note
        import warnings
        warnings.warn(
            "python-json-logger not installed. JSON log format unavailable. "
            "Install with: pip install python-json-logger>=2.0",
            stacklevel=3,
        )
        return logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def _get_colored_formatter() -> logging.Formatter:
    """Return a colored formatter for development console output.

    Uses colorlog if available; falls back to plain text formatting.
    """
    try:
        import colorlog

        return colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)-8s]%(reset)s "
            "%(blue)s%(name)s%(reset)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    except ImportError:
        # Fallback: plain text (works everywhere)
        return logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
