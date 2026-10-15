"""Input DTO for the get_table_catalog tool: filtered, paginated catalog query."""

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass

# src/ is on sys.path, so the domain package is imported as "domain".
from domain.value_objects.pagination import DEFAULT_PAGE_SIZE


# Both boundary dtos share one convention: strict pydantic dataclasses. The
# extra="forbid" config is what makes an unexpected key a loud schema error
# instead of a value pydantic would silently drop.
@pydantic_dataclass(frozen=True, slots=True, config=ConfigDict(extra="forbid"))
class TableCatalogQuery:
    """Input data carrier for a filtered, paginated table catalog query.

    Pure data, flat primitives: no business validation here and no domain
    object leaks. Rules for incoming dtos live in a dedicated validator that
    returns a Result.

    Attributes:
        schema: Optional schema name to filter tables by. ``None`` means
            "no schema filter": the repository decides the dialect's effective
            default (e.g. public in Postgres, dbo in SQL Server).
        page: 1-based page number.
        page_size: Number of rows per page.
    """

    schema: str | None = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
