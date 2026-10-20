"""Widen raw driver values into JSON-safe Python types.

The MCP layer serializes tool results with the standard JSON encoder, which
chokes on the types drivers happily return (Decimal, datetime, UUID, bytes).
This module converts them at the slice edge — per AGENTS.md, widening belongs
to the slice that returns the rows, never deep inside ``shared``.

The conversion is deliberately TOTAL: anything it does not recognize falls
back to ``str(value)``, so a single exotic column type can never crash the
tool.
"""

from __future__ import annotations

import base64
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID


def to_json_safe(value: Any) -> Any:
    """Return ``value`` widened into a JSON-native Python type.

    Conversion table:

    * ``None``, ``bool``, ``int``, ``float``, ``str`` — unchanged.
    * ``list`` / ``tuple`` — recursed element-wise (rows, nested arrays).
    * ``dict`` — keys and values recursed.
    * ``Decimal`` — converted to ``float``. JSON has no decimal type, so
      this is a widening to the nearest representable float: values too
      precise for a double lose precision in flight. Callers that need
      exactness should cast the column to text in the SQL itself.
    * ``datetime`` / ``date`` / ``time`` — ISO 8601 string via
      ``isoformat()``.
    * ``UUID`` — canonical string form.
    * ``bytes`` / ``bytearray`` / ``memoryview`` — base64 ASCII string
      (binary has no JSON representation; base64 is lossless).
    * anything else — ``str(value)`` as a last resort: a tool must answer,
      never crash on an exotic driver type.
    """
    # bool is a subclass of int, so it must appear (and match) first:
    # True/False must survive as JSON true/false, never become 1/0.
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {
            to_json_safe(key): to_json_safe(item) for key, item in value.items()
        }
    # datetime is a subclass of date; the tuple handles all three uniformly.
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    # Unrecognized driver type: widen to its string form rather than raise —
    # an exotic value must degrade the payload, never fail the whole tool.
    return str(value)
