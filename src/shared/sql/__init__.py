"""Cross-cutting SQL concerns shared by every slice (read-only guard)."""

from .read_only import ensure_read_only

__all__ = ["ensure_read_only"]
