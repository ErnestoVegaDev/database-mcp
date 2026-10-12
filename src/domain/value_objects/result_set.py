"""Immutable query result value object."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

# Relative imports: one dot = current package, two dots = parent package.
from ..enums import ColumnType
from .record import Record


# Same sealing contract as Record: frozen reference + read-only contents.
@dataclass(frozen=True, slots=True)
class ResultSet:
    """Immutable query result: column types declared once + records."""

    # tuple[Record, ...]: an immutable sequence of Records. The `...` (Ellipsis)
    # is just typing syntax for "any number of these items".
    columns: Mapping[str, ColumnType]
    records: tuple[Record, ...]

    # Called automatically after the fields are assigned; never runs if
    # construction fails, so a broken ResultSet simply cannot exist.
    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", MappingProxyType(dict(self.columns)))
        # dict_keys comparison is set-like: order is ignored, only membership
        # matters, so this validates that every record exposes exactly the
        # declared columns (no missing, no extra).
        for record in self.records:
            if record.values.keys() != self.columns.keys():
                # raise aborts construction with a domain-level error.
                raise ValueError("record columns do not match result columns")
