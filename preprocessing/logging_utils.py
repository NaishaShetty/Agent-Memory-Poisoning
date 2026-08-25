"""Shared logging setup for the preprocessing pipeline.

All pipeline runs log to both stderr and a per-run file under
data/logs/, so preprocessing behavior is auditable after the fact.
"""
from __future__ import annotations

import logging
from pathlib import Path


def get_logger(name: str, logs_dir: Path | None = None, run_id: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers)

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    if logs_dir is not None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run_id}.log" if run_id else f"{name}.log"
        file_handler = logging.FileHandler(logs_dir / filename, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger
