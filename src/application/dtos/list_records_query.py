"""Input DTO for a filtered, paginated, projected list query."""

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass

from .filter_criterion_query import FilterCriterionQuery

# src/ is on sys.path, so the domain package is imported as "domain".
from domain.value_objects.pagination import DEFAULT_PAGE_SIZE


# Same strict contract as FilterCriterionQuery: extra="forbid" is what stops a
# typo in a filter from silently returning unfiltered data, because pydantic
# would otherwise drop the unknown key without raising.
@pydantic_dataclass(frozen=True, slots=True, config=ConfigDict(extra="forbid"))
class ListRecordsQuery:
    """Input data carrier for a filtered, paginated, projected list query.

    Pure data, flat primitives: no business validation here and no domain
    object leaks. Rules for incoming dtos live in a dedicated validator that
    returns a Result.

    Attributes:
        table: Target table to read from.
        columns: Columns to reveal, in the requested order.
        schema: Optional schema that owns the table. ``None`` means the
            repository resolves the dialect's effective default (e.g. public
            in Postgres, dbo in SQL Server).
        filters: AND-combined predicates. Empty means every row matches.
        page: 1-based page number.
        page_size: Number of rows per page.
    """

    table: str
    columns: tuple[str, ...]
    schema: str | None = None
    filters: tuple[FilterCriterionQuery, ...] = ()
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        # Not validation: enforces the DTO's own immutability invariant. A
        # JSON client sends arrays, so re-seal them as tuples; "is this a legal
        # value?" stays the validator's question.
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "filters", tuple(self.filters))
