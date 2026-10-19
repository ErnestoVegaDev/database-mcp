"""A requested entity does not exist."""

from dataclasses import dataclass

from .domain_error import DomainError


@dataclass(frozen=True, slots=True)
class NotFoundError(DomainError):
    """A well-formed lookup that matched no entity.

    A missing row or schema is an expected outcome, not a bug, so it travels
    as a Failure instead of an empty result the caller has to special-case.

    Attributes:
        message: Human-readable description.
        entity: Kind of thing that was missing (e.g. ``table``, ``schema``).
        key: Identifier that failed to resolve, rendered as text.
    """

    entity: str = ""
    key: str | None = None
