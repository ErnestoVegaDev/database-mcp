"""Logical database column types."""

from enum import StrEnum


# StrEnum (Python 3.11+): every member is both an enum member and its string
# value, so ColumnType.TEXT == "text" and json.dumps serializes it directly.
class ColumnType(StrEnum):
    """Logical column types, independent of any ORM."""

    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    JSON = "json"
    BINARY = "binary"
    UNKNOWN = "unknown"
