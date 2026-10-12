"""Immutable single-column filter predicate."""

# Iterable is the ABC used to accept any sequence-like operand for IN / NOT_IN.
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# Relative import: two dots = parent package (domain), so FilterOperator is
# resolved from the re-exported enums package.
from ..enums import FilterOperator


# Same sealing contract as the other domain value objects: frozen reference +
# validated contents, and slots for a fixed memory layout.
@dataclass(frozen=True, slots=True)
class FilterCriterion:
    """One predicate: a column, an operator, and an optional operand.

    A criterion is descriptive data, not a query: it says *what* to match,
    never *how* a given database should execute it. Translating it into SQL
    is the persistence adapter's job.
    """

    column: str
    operator: FilterOperator
    value: Any = None

    # __post_init__ runs right after the generated __init__ assigns the fields,
    # so every invalid criterion fails at construction and cannot exist.
    def __post_init__(self) -> None:
        if not self.column:
            raise ValueError("column must be a non-empty string")
        if not isinstance(self.operator, FilterOperator):
            raise TypeError("operator must be a FilterOperator")

        # IS NULL / IS NOT NULL are unary: they must not carry an operand, so
        # any value that slipped in is normalized away instead of rejected.
        # object.__setattr__ bypasses frozen=True, which would otherwise raise.
        if not self.operator.needs_value:
            object.__setattr__(self, "value", None)
            return

        if self.value is None:
            raise ValueError(f"operator {self.operator.value} requires a value")

        # IN / NOT IN compare against a set, not a single value: coerce to an
        # immutable tuple. Strings are rejected because "abc" is a sequence,
        # but almost never the intended set of members.
        if self.operator in (FilterOperator.IN, FilterOperator.NOT_IN):
            if isinstance(self.value, (str, bytes)) or not isinstance(
                self.value, Iterable
            ):
                raise TypeError("IN / NOT_IN require a non-string sequence")
            members = tuple(self.value)
            if not members:
                raise ValueError("IN / NOT_IN require at least one value")
            object.__setattr__(self, "value", members)
