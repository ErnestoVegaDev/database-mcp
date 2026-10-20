"""Render a domain error as the MCP edge's error envelope.

Expected failures reach the client in one fixed shape (decision D5)::

    {"status": "error", "error": {"type": ..., "message": ..., ...}}

This module is only responsible for the *shape*. It never invents message text
and never touches a connection string: producing a DSN-free message is the
producer's contract, and the factory already sanitizes driver failures down to
the exception class name before any error reaches here.
"""

from __future__ import annotations

from typing import Any

from .domain_error import DomainError
from .not_found_error import NotFoundError
from .validation_error import ValidationError, ValidationErrors


def error_payload(error: DomainError) -> dict[str, Any]:
    """Render ``error`` as ``{"status": "error", "error": {...}}``.

    The error body always carries the error's class name (``type``) and its
    ``message``. Subclass detail is added when present: ``field`` for a
    :class:`ValidationError`, the individual violations for a
    :class:`ValidationErrors`, and ``entity``/``key`` for a
    :class:`NotFoundError`. Fields that hold no useful value are omitted
    rather than sent as empty noise.

    Args:
        error: The expected failure to render.

    Returns:
        The D5 envelope ready to be returned from a tool.
    """
    body: dict[str, Any] = {
        "type": type(error).__name__,
        "message": error.message,
    }

    if isinstance(error, ValidationErrors):
        body["errors"] = [
            {
                "type": type(violation).__name__,
                "message": violation.message,
                **({"field": violation.field} if violation.field else {}),
            }
            for violation in error.errors
        ]
    elif isinstance(error, ValidationError) and error.field:
        body["field"] = error.field

    if isinstance(error, NotFoundError):
        if error.entity:
            body["entity"] = error.entity
        if error.key is not None:
            body["key"] = error.key

    return {"status": "error", "error": body}
