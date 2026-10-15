"""Wire mirror of the domain FilterCriterion: one predicate as sent by a client."""

from typing import Any

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass

# src/ is on sys.path, so the domain package is imported as "domain".
from domain.enums import FilterOperator


# extra="forbid" is mandatory here: pydantic silently DROPS an unknown key by
# default, so a mistyped predicate would turn into a silently unfiltered query
# that returns every row with no error. Rejecting extras turns that typo into a
# loud schema error at the boundary instead of wrong data at the caller.
@pydantic_dataclass(frozen=True, slots=True, config=ConfigDict(extra="forbid"))
class FilterCriterionQuery:
    """A single filter predicate exactly as it arrives from the client.

    Pure descriptive data: it says *what* to match and never builds SQL. The
    persistence adapter is the only layer allowed to translate a predicate into
    a dialect's own syntax.

    Attributes:
        column: Column the predicate applies to.
        operator: Comparison to apply.
        value: Operand the operator compares against. Deliberately typed
            ``Any``: pydantic does not coerce ``Any``, so the client literal is
            preserved exactly (5 stays an int, "5" stays a str, True stays a
            bool). Coercing here would silently change the query, because 5 and
            "5" are different comparisons.
    """

    # Whether an operator accepts a value, and which value shapes it accepts,
    # is enforced by the validator rather than by this schema: a per-operator
    # rule is a business rule about the request, and only the validator can
    # report it as a structured validation failure the caller can act on.
    column: str
    operator: FilterOperator
    value: Any = None
