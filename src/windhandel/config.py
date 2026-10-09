"""
Environment configuration and logging setup.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------
# API location
# --------------------------------------------------------------------------

API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_BASE: str = f"http://{API_HOST}:{API_PORT}"
API_STARTUP_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "30"))

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR: Path = Path(os.getenv("LOG_DIR"))


def log_path(name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"{name}.log"


def configure_logging(name: str) -> Path:
    """
    Attach a rotating file handler to the root logger.
    """
    path = log_path(name)
    handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    # Idempotent: re-importing or re-calling must not double every log line.
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    return path