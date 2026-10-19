"""Input that violates a business rule."""

from dataclasses import dataclass

from .domain_error import DomainError


@dataclass(frozen=True, slots=True)
class ValidationError(DomainError):
    """One rule violation, tied to the field that broke it.

    Attributes:
        message: Which rule was broken.
        field: Name of the offending input field, when it maps to one.
    """

    field: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationErrors(DomainError):
    """Every rule violation found in one request, reported together.

    Validation collects instead of failing fast, so a caller fixes all the
    problems in a single round trip instead of discovering them one by one.

    Attributes:
        message: Summary of the failure.
        errors: The individual violations, in the order they were found.
    """

    errors: tuple[ValidationError, ...] = ()

    def __str__(self) -> str:
        return "; ".join(
            f"{error.field}: {error.message}" if error.field else error.message
            for error in self.errors
        )
