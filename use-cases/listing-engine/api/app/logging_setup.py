from __future__ import annotations

import logging
import sys

import structlog


def configure(git_commit: str, use_case: str) -> None:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
    )
    structlog.contextvars.bind_contextvars(git_commit=git_commit, use_case=use_case)
