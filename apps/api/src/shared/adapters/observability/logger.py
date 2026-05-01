from __future__ import annotations

import contextvars
import logging
import sys
from typing import Any

import structlog

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_context", default=None  # type: ignore[arg-type]
)


def _merge_context(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    ctx = _context.get() or {}
    for k, v in ctx.items():
        event_dict.setdefault(k, v)
    return event_dict


def configure_logging(*, level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        level=level.upper(),
        stream=sys.stdout,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _merge_context,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name or "nexoia")


def bind_context(**kwargs: Any) -> None:
    current = dict(_context.get() or {})
    current.update({k: v for k, v in kwargs.items() if v is not None})
    _context.set(current)


def reset_context() -> None:
    _context.set({})
