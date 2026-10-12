"""Immutable pagination value object."""

from dataclasses import dataclass

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# frozen=True  -> immutable after construction; slots=True -> no ad-hoc attributes.
@dataclass(frozen=True, slots=True)
class Pagination:
    """Client-facing pagination (page/page_size) with SQL-facing accessors.

    page is 1-based; offset is derived so callers cannot express an
    inconsistent page/offset pair.
    """

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if isinstance(self.page, bool) or not isinstance(self.page, int):
            raise TypeError("page must be an integer")
        if isinstance(self.page_size, bool) or not isinstance(self.page_size, int):
            raise TypeError("page_size must be an integer")
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

    # @property exposes the method as attribute-style access: pagination.offset.
    # Computed from page/page_size, so a Pagination can never hold a stale or
    # contradictory offset value.
    @property
    def offset(self) -> int:
        """Return the SQL OFFSET value derived from the page number."""
        return (self.page - 1) * self.page_size
