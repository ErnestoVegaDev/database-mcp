"""Comparison operators available to domain-level filters."""

from enum import StrEnum


# StrEnum (Python 3.11+): each member is also its string value, so
# FilterOperator.EQ == "eq" and the enum serializes to JSON directly.
class FilterOperator(StrEnum):
    """Comparison operators a FilterCriterion can use.

    These are logical operators, not SQL syntax: the persistence adapter is
    the one that translates each member into the dialect's own operator.
    """

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"

    @property
    def needs_value(self) -> bool:
        """Return whether the operator requires an operand value."""
        # IS NULL / IS NOT NULL are unary: they take no operand, so they are
        # the only members that do not need a value.
        return self not in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL)
