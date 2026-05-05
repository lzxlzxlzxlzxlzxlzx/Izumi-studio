"""
Logging configuration — writes to file and console.
"""

import logging
from logging.handlers import RotatingFileHandler
from app.config import settings


def setup_logging():
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (rotating: 10 MB x 5 backups)
    file_handler = RotatingFileHandler(
        str(settings.logs_dir / "backend.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    # Apply to root logger (catches all app loggers)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Also capture uvicorn logs
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = False
        uvicorn_logger.setLevel(logging.INFO)
        uvicorn_logger.addHandler(file_handler)
        uvicorn_logger.addHandler(console_handler)

    # Suppress noisy library logs
    for name in ("httpx", "httpcore.http11", "httpcore.connection", "httpcore.proxy",
                 "sse_starlette.sse", "watchfiles"):
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(logging.WARNING)
