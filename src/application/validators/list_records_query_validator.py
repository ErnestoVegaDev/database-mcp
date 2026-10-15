"""Validates a ListRecordsQuery before it reaches the domain."""

from typing import Any

from application.dtos import FilterCriterionQuery, ListRecordsQuery
from domain.enums import FilterOperator
from domain.errors import DomainError, ValidationError, ValidationErrors
from domain.value_objects.pagination import MAX_PAGE_SIZE
from returns.result import Failure, Result, Success

# The value types a single-column comparison can carry. bool is a subclass of
# int, but it is also a legitimate scalar: a boolean column can be compared with
# eq, so it is listed explicitly rather than relying on the int relationship.
_SCALAR_TYPES = (str, int, float, bool)

# Operators that compare one column against a single operand value.
_COMPARISON_OPERATORS = (
    FilterOperator.EQ,
    FilterOperator.NE,
    FilterOperator.GT,
    FilterOperator.GTE,
    FilterOperator.LT,
    FilterOperator.LTE,
)


def _is_scalar(value: Any) -> bool:
    """Return whether value is a plain scalar: never None, never a container."""
    return value is not None and isinstance(value, _SCALAR_TYPES)


class ListRecordsQueryValidator:
    """Turns an untrusted list query DTO into either a valid DTO or a Failure.

    Rules are checked in one pass so every violation is reported at once. The
    numeric bounds come from the same constants the Pagination value object
    enforces, so the limits keep a single source of truth.

    The per-operator value contract lives here and not in the DTO schema:
    "does this operator accept a value?" is a business rule about the request,
    and only the boundary can report it as a structured validation failure
    instead of a shape error.
    """

    def validate(
        self, query: ListRecordsQuery
    ) -> Result[ListRecordsQuery, DomainError]:
        """Return ``Success(query)`` or ``Failure(ValidationErrors(...))``."""
        errors: list[ValidationError] = []
        errors.extend(self._validate_shape(query))
        errors.extend(self._validate_filters(query.filters))

        if errors:
            return Failure(
                ValidationErrors(
                    f"{len(errors)} invalid field(s)", errors=tuple(errors)
                )
            )
        return Success(query)

    def _validate_shape(self, query: ListRecordsQuery) -> list[ValidationError]:
        """Check the non-filter fields: table, schema, columns, pagination."""
        errors: list[ValidationError] = []

        if not query.table.strip():
            errors.append(ValidationError("table must not be blank", field="table"))
        if query.schema is not None and not query.schema.strip():
            errors.append(
                ValidationError(
                    "schema must not be blank when provided", field="schema"
                )
            )

        if not query.columns:
            errors.append(
                ValidationError(
                    "columns must contain at least one name", field="columns"
                )
            )

        seen: set[str] = set()
        for index, column in enumerate(query.columns):
            if not column.strip():
                errors.append(
                    ValidationError(
                        "column name must not be blank", field=f"columns[{index}]"
                    )
                )
                continue
            if column in seen:
                errors.append(
                    ValidationError(
                        f"column '{column}' is duplicated", field=f"columns[{index}]"
                    )
                )
                continue
            seen.add(column)

        if query.page < 1:
            errors.append(ValidationError("page must be >= 1", field="page"))
        if not 1 <= query.page_size <= MAX_PAGE_SIZE:
            errors.append(
                ValidationError(
                    f"page_size must be between 1 and {MAX_PAGE_SIZE}",
                    field="page_size",
                )
            )

        return errors

    def _validate_filters(
        self, filters: tuple[FilterCriterionQuery, ...]
    ) -> list[ValidationError]:
        """Check every criterion, tagging each finding with its index."""
        errors: list[ValidationError] = []
        for index, criterion in enumerate(filters):
            errors.extend(self._validate_criterion(index, criterion))
        return errors

    def _validate_criterion(
        self, index: int, criterion: FilterCriterionQuery
    ) -> list[ValidationError]:
        """Check one criterion: its column name and its operator/value pair."""
        prefix = f"filters[{index}]"
        errors: list[ValidationError] = []

        if not criterion.column.strip():
            errors.append(
                ValidationError(
                    "filter column must not be blank", field=f"{prefix}.column"
                )
            )
        errors.extend(self._validate_criterion_value(prefix, criterion))
        return errors

    def _validate_criterion_value(
        self, prefix: str, criterion: FilterCriterionQuery
    ) -> list[ValidationError]:
        """Enforce the value contract of the criterion's operator."""
        field = f"{prefix}.value"
        operator = criterion.operator
        value = criterion.value

        # Unary operators accept no operand. The domain normalizes a stray value
        # away, but the boundary rejects it: accepting it would silently drop
        # input the caller believed was used. Reject at the boundary, guarantee
        # the invariant in the domain.
        if not operator.needs_value:
            if value is not None:
                return [
                    ValidationError(
                        f"operator '{operator.value}' does not accept a value",
                        field=field,
                    )
                ]
            return []

        if value is None:
            return [
                ValidationError(
                    f"operator '{operator.value}' requires a value", field=field
                )
            ]

        if operator in (FilterOperator.IN, FilterOperator.NOT_IN):
            return self._validate_membership(prefix, operator, value)

        if operator is FilterOperator.LIKE:
            if not isinstance(value, str):
                return [
                    ValidationError(
                        "operator 'like' requires a string pattern", field=field
                    )
                ]
            return []

        if operator in _COMPARISON_OPERATORS and not _is_scalar(value):
            return [
                ValidationError(
                    f"operator '{operator.value}' requires a scalar value",
                    field=field,
                )
            ]

        return []

    def _validate_membership(
        self, prefix: str, operator: FilterOperator, value: Any
    ) -> list[ValidationError]:
        """Check the member list of an IN / NOT_IN criterion."""
        field = f"{prefix}.value"
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
            return [
                ValidationError(
                    f"operator '{operator.value}' requires a list of values",
                    field=field,
                )
            ]
        if not value:
            return [
                ValidationError(
                    f"operator '{operator.value}' requires at least one value",
                    field=field,
                )
            ]

        errors: list[ValidationError] = []
        for member_index, member in enumerate(value):
            member_field = f"{field}[{member_index}]"
            if member is None:
                # SQL three-valued logic: NOT IN (NULL) never matches, so a NULL
                # member would silently return zero rows. Point the caller at
                # the unary operator that expresses the real intent instead.
                errors.append(
                    ValidationError(
                        "members must not be None; use the 'is_null' or "
                        "'is_not_null' operator instead",
                        field=member_field,
                    )
                )
            elif not _is_scalar(member):
                errors.append(
                    ValidationError(
                        "members must be scalars (str, int, float or bool)",
                        field=member_field,
                    )
                )
        return errors
