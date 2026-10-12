"""Immutable database row value object."""

# dataclass generates __init__, __eq__ and __repr__ from the field annotations.
from dataclasses import dataclass
# MappingProxyType wraps a dict in a read-only view (mutation raises TypeError).
from types import MappingProxyType
# Any = any type; Mapping = any dict-like object; Iterator = something iterable once.
from typing import Any, Iterator, Mapping


# frozen=True  -> instances are immutable: attribute assignment raises
#                 FrozenInstanceError after construction.
# slots=True   -> instances get a fixed slot per field instead of a __dict__,
#                 which blocks ad-hoc attributes and saves memory per object.
@dataclass(frozen=True, slots=True)
class Record:
    """Immutable row: column values only. Types live in ResultSet."""

    # Dataclass field declaration. Mapping[str, Any] reads as "a dict-like
    # object with string keys and values of any type". Type hints are NOT
    # enforced at runtime: Python will not stop you from passing anything.
    values: Mapping[str, Any]

    # __post_init__ is a dataclass hook called automatically right after the
    # generated __init__ assigns the fields. We use it to seal the dict:
    #
    #   dict(self.values)       -> private copy, so the caller keeps no
    #                              reference into our internals
    #   MappingProxyType(...)   -> read-only view over that copy; any
    #                              mutation attempt raises TypeError
    #   object.__setattr__(...) -> bypasses the restriction frozen=True
    #                              installs, because a plain assignment here
    #                              (self.values = ...) would raise
    #                              FrozenInstanceError
    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    # Dunder methods are language hooks, not ordinary methods: defining
    # __getitem__ is what makes record["id"] work. It delegates to the mapping.
    def __getitem__(self, column: str) -> Any:
        """Return the value of a column."""
        return self.values[column]

    # Ordinary method: same as record[column] but returns `default` instead
    # of raising KeyError when the column is absent.
    def get(self, column: str, default: Any = None) -> Any:
        """Return the value of a column or a default."""
        return self.values.get(column, default)

    # __iter__ makes `for column, value in record:` work. Returning an
    # iterator of (key, value) pairs delegates iteration to the mapping.
    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Iterate over (column, value) pairs."""
        return iter(self.values.items())

    # __len__ makes len(record) work and returns the column count.
    def __len__(self) -> int:
        """Return the number of columns."""
        return len(self.values)

    # @property converts a method into attribute-style access, so callers
    # write record.columns instead of record.columns(). tuple(...) snapshots
    # the names so the result cannot change if the mapping ever does.
    @property
    def columns(self) -> tuple[str, ...]:
        """Return the column names in order."""
        return tuple(self.values.keys())
