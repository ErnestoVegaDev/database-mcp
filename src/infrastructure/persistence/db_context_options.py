"""Configuration for the async database context.

This module owns the *how* of the DbContext: the connection string and the
timeout/pooling knobs. It deliberately imports no SQLAlchemy — it is a plain
configuration carrier, so it can be validated and unit-tested without a
database and without an event loop.

The object is assembled with a small fluent builder. Every ``with_*`` method
returns a NEW builder instead of mutating the current one, so the whole thing
stays immutable and safe to share. ``build()`` is the only place that validates.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

# Environment variable names. The unit is part of the name on purpose: a
# timeout called just "TIMEOUT" is a bug waiting for its turn. The MCP_DB_
# prefix namespaces them so they cannot collide with unrelated variables.
ENV_CONNECTION_STRING = "MCP_DB_CONNECTION_STRING"
ENV_POOL_TIMEOUT_SECONDS = "MCP_DB_POOL_TIMEOUT_SECONDS"
ENV_CONNECT_TIMEOUT_SECONDS = "MCP_DB_CONNECT_TIMEOUT_SECONDS"
ENV_ECHO = "MCP_DB_ECHO"

# SQLAlchemy's own default for pool_timeout, restated so the builder and the
# engine agree on a single number.
DEFAULT_POOL_TIMEOUT_SECONDS = 30.0

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    """Read an optional float env var, falling back to ``default`` when unset."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _env_optional_float(name: str) -> float | None:
    """Read an optional float env var; ``None`` when unset or blank."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean env var from the usual truthy/falsy spellings."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    raise ValueError(f"{name} must be one of {sorted(_TRUTHY | _FALSY)}, got {raw!r}")


@dataclass(frozen=True, slots=True)
class DbContextOptions:
    """Validated, immutable configuration for :class:`DbContext`.

    Build it directly for tests::

        DbContextOptions(connection_string="sqlite+aiosqlite:///:memory:")

    through the fluent builder when you have several options::

        (DbContextOptions.builder()
            .with_connection_string(dsn)
            .with_pool_timeout_seconds(10)
            .build())

    or from the process environment (the variables an MCP client declares in
    its server ``env`` block)::

        DbContextOptions.from_env()
    """

    # repr=False keeps the connection string (and its password) out of logs,
    # tracebacks and error messages. Everything else is safe to print.
    connection_string: str = field(repr=False)

    # How long a caller waits for a free connection from the pool before
    # SQLAlchemy raises. Driver-agnostic: SQLAlchemy itself enforces it.
    pool_timeout_seconds: float = DEFAULT_POOL_TIMEOUT_SECONDS

    # How long the driver waits to OPEN a new connection. Optional, because it
    # is driver-specific: asyncpg and pyodbc both accept ``timeout``, aiosqlite
    # ignores it. None means "leave the driver default alone".
    connect_timeout_seconds: float | None = None

    # Log every SQL statement. Debugging aid; noisy in production.
    echo: bool = False

    def __post_init__(self) -> None:
        """Reject invalid options at construction time (fail fast)."""
        if not self.connection_string.strip():
            raise ValueError(
                "connection_string is required and must be non-empty. Pass it "
                f"to the builder or set the {ENV_CONNECTION_STRING} environment variable."
            )
        if self.pool_timeout_seconds <= 0:
            raise ValueError(
                f"pool_timeout_seconds must be > 0, got {self.pool_timeout_seconds!r}. "
                f"Check {ENV_POOL_TIMEOUT_SECONDS}."
            )
        if self.connect_timeout_seconds is not None and self.connect_timeout_seconds <= 0:
            raise ValueError(
                "connect_timeout_seconds must be > 0 when set, got "
                f"{self.connect_timeout_seconds!r}. Check {ENV_CONNECT_TIMEOUT_SECONDS}."
            )

    @staticmethod
    def builder() -> "DbContextOptionsBuilder":
        """Start a fluent, immutable builder."""
        return DbContextOptionsBuilder()

    @classmethod
    def from_env(cls) -> "DbContextOptions":
        """Build options from the process environment.

        Reads ``MCP_DB_CONNECTION_STRING`` (required),
        ``MCP_DB_POOL_TIMEOUT_SECONDS``, ``MCP_DB_CONNECT_TIMEOUT_SECONDS`` and
        ``MCP_DB_ECHO``.

        Raises:
            ValueError: when a required variable is missing or a value is
                malformed. Failing here beats a cryptic driver error later.
        """
        return (
            cls.builder()
            .with_connection_string(os.environ.get(ENV_CONNECTION_STRING, ""))
            .with_pool_timeout_seconds(
                _env_float(ENV_POOL_TIMEOUT_SECONDS, DEFAULT_POOL_TIMEOUT_SECONDS)
            )
            .with_connect_timeout_seconds(_env_optional_float(ENV_CONNECT_TIMEOUT_SECONDS))
            .with_echo(_env_bool(ENV_ECHO, False))
            .build()
        )

    @classmethod
    def from_env_or_none(cls) -> "DbContextOptions | None":
        """Build options from the environment, or ``None`` when no DB is configured.

        This is the "is a database configured?" seam: the knowledge of WHICH
        variable decides that lives here with the rest of the environment rules,
        not as a raw ``os.environ`` read in the composition root. A caller that
        must choose between a real adapter and a stand-in asks this method and
        branches on ``None``.

        Unlike :meth:`from_env`, an absent connection string is not an error
        here; it means "not configured". A present-but-malformed value still
        raises, because that is a misconfiguration worth surfacing loudly.
        """
        # A blank or whitespace-only value counts as unset, matching the
        # builder's own strip() so "MCP_DB_CONNECTION_STRING=" behaves like unset.
        if not os.environ.get(ENV_CONNECTION_STRING, "").strip():
            return None
        return cls.from_env()


@dataclass(frozen=True, slots=True)
class DbContextOptionsBuilder:
    """Fluent, immutable builder for :class:`DbContextOptions`.

    Each ``with_*`` returns a new builder, so a half-configured builder can be
    shared and branched without aliasing surprises::

        base = DbContextOptions.builder().with_connection_string(dsn)
        fast = base.with_pool_timeout_seconds(5).build()
        slow = base.with_pool_timeout_seconds(60).build()
    """

    # Private, all-optional staging fields. They only become a validated
    # DbContextOptions in build(); a partial state never raises on its own.
    _connection_string: str = field(default="", repr=False)
    _pool_timeout_seconds: float = DEFAULT_POOL_TIMEOUT_SECONDS
    _connect_timeout_seconds: float | None = None
    _echo: bool = False

    def with_connection_string(self, connection_string: str) -> "DbContextOptionsBuilder":
        """Set the SQLAlchemy connection URL (the async driver is in the scheme)."""
        return replace(self, _connection_string=connection_string)

    def with_pool_timeout_seconds(self, seconds: float) -> "DbContextOptionsBuilder":
        """Set how long to wait for a free pooled connection."""
        return replace(self, _pool_timeout_seconds=seconds)

    def with_connect_timeout_seconds(self, seconds: float | None) -> "DbContextOptionsBuilder":
        """Set the driver-level connect timeout (None leaves the driver default)."""
        return replace(self, _connect_timeout_seconds=seconds)

    def with_echo(self, echo: bool = True) -> "DbContextOptionsBuilder":
        """Turn SQL statement logging on (default) or off."""
        return replace(self, _echo=echo)

    def build(self) -> DbContextOptions:
        """Validate the staged values and produce the immutable options.

        Raises:
            ValueError: if any staged value is invalid (see
                :meth:`DbContextOptions.__post_init__`).
        """
        return DbContextOptions(
            connection_string=self._connection_string.strip(),
            pool_timeout_seconds=self._pool_timeout_seconds,
            connect_timeout_seconds=self._connect_timeout_seconds,
            echo=self._echo,
        )
