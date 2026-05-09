from __future__ import annotations

import logging
import sys

import structlog


def mask_phone(phone: str | None) -> str:
    """Mask phone for safe logging: +9665***6789 style."""
    if not phone:
        return ""
    if len(phone) <= 4:
        return "****"
    return phone[:5] + "***" + phone[-2:]


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "baytseha") -> structlog.BoundLogger:
    return structlog.get_logger(name)
