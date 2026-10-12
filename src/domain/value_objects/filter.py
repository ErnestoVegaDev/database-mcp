"""Immutable, AND-combined set of filter criteria."""

from dataclasses import dataclass

from .filter_criterion import FilterCriterion


@dataclass(frozen=True, slots=True)
class Filter:
    """An immutable collection of predicates combined with AND.

    An empty Filter means "no filtering": every row matches. This type is the
    seam where OR groups or nested conditions can grow later without touching
    any repository method signature.
    """

    criteria: tuple[FilterCriterion, ...] = ()

    def __post_init__(self) -> None:
        # Coerce any sequence into an immutable tuple; a caller passing a list
        # keeps no reference into our internals.
        object.__setattr__(self, "criteria", tuple(self.criteria))

    def __bool__(self) -> bool:
        """Return whether the filter actually constrains anything."""
        return bool(self.criteria)
