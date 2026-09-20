"""
InfoSphere Cyber Live Wallpaper Engine
core/logger.py

Sets up a rotating-file logger that also writes to stdout.
The logs/ folder is created automatically if it does not exist.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(log_path: str = "logs/wallpaper.log") -> logging.Logger:
    """
    Create and return the 'InfoSphere' application logger.

    Parameters
    ----------
    log_path : str
        Relative or absolute path for the log file.

    Returns
    -------
    logging.Logger
        Configured logger with both file and console handlers.
    """

    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("InfoSphere")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if called more than once
    if logger.handlers:
        logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ── Rotating file handler (max 5 MB, keep 3 old files) ────────────────
    try:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as exc:
        print(f"[InfoSphere] WARNING  Cannot create log file ({exc}). File logging disabled.")

    # ── Console handler ────────────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
