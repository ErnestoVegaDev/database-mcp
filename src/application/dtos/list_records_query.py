"""Input DTO for a paginated, projected list query."""

from dataclasses import dataclass

# src/ is on sys.path, so the domain package is imported as "domain".
from domain.value_objects.pagination import DEFAULT_PAGE_SIZE


@dataclass(frozen=True, slots=True)
class ListRecordsQuery:
    """Input data carrier for a paginated, projected list query.

    Pure data, flat primitives: no business validation here and no domain
    object leaks. Rules for incoming dtos live in a dedicated validator that
    returns a Result.

    Attributes:
        columns: Names of the columns to reveal.
        page: 1-based page number.
        page_size: Number of rows per page.
    """

    columns: tuple[str, ...]
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        # Not validation: enforces the DTO's own immutability invariant.
        object.__setattr__(self, "columns", tuple(self.columns))
