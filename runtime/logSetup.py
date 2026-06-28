# -*- coding: utf-8 -*-
# ── Logging Setup ───────────────────────────────────────────────────────────
#
# Configures root logger with console + optional file handler.
# Called once at startup.

import logging
import sys
from pathlib import Path


def configureLogging(level: int = logging.INFO, logDir: Path | None = None) -> None:
    """Configure root logger with console output and optional file rotation."""
    rootLogger = logging.getLogger()
    rootLogger.setLevel(level)

    # clear existing handlers (re-entrant safe)
    rootLogger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)
    rootLogger.addHandler(console)

    # file handler (if logDir provided)
    if logDir is not None:
        logDir.mkdir(parents=True, exist_ok=True)
        filePath = logDir / "dhe.log"
        fileHandler = logging.FileHandler(filePath, encoding="utf-8", mode="a")
        fileHandler.setFormatter(fmt)
        fileHandler.setLevel(logging.DEBUG)
        rootLogger.addHandler(fileHandler)
