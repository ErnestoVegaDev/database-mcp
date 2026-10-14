"""Validates a TableCatalogQuery before it reaches the domain."""

from application.dtos import TableCatalogQuery
from domain.errors import DomainError, ValidationError, ValidationErrors
from domain.value_objects.pagination import MAX_PAGE_SIZE
from returns.result import Failure, Result, Success


class TableCatalogQueryValidator:
    """Turns an untrusted query DTO into either a valid DTO or a Failure.

    Rules are checked in one pass so every violation is reported at once.
    The numeric bounds come from the same constants the Pagination value
    object enforces, so the limits keep a single source of truth.
    """

    def validate(
        self, query: TableCatalogQuery
    ) -> Result[TableCatalogQuery, DomainError]:
        """Return ``Success(query)`` or ``Failure(ValidationErrors(...))``."""
        errors: list[ValidationError] = []

        if query.schema is not None and not query.schema.strip():
            errors.append(
                ValidationError(
                    "schema must not be blank when provided", field="schema"
                )
            )
        if query.page < 1:
            errors.append(ValidationError("page must be >= 1", field="page"))
        if not 1 <= query.page_size <= MAX_PAGE_SIZE:
            errors.append(
                ValidationError(
                    f"page_size must be between 1 and {MAX_PAGE_SIZE}",
                    field="page_size",
                )
            )

        if errors:
            return Failure(
                ValidationErrors(
                    f"{len(errors)} invalid field(s)", errors=tuple(errors)
                )
            )
        return Success(query)
