"""Base type for expected domain failures."""

from dataclasses import dataclass


# An expected failure is data, not an exception: it can travel inside a
# Result, be inspected by the caller, and be serialized at the MCP edge.
# Genuine bugs (a broken invariant, a lost connection) keep raising and stay
# unhandled, so this hierarchy never swallows something it cannot explain.
@dataclass(frozen=True, slots=True)
class DomainError:
    """An anticipated failure that a caller can act on.

    Attributes:
        message: Human-readable description of what went wrong.
    """

    message: str

    def __str__(self) -> str:
        return self.message
