"""The environment contract for database connections.

This module is the single place that turns the process environment into
validated :class:`ConnectionOptions`. One environment variable per supported
engine decides whether that engine is configured:

* ``POSTGRES_CONNECTION_STRING`` — async PostgreSQL URL
* ``MARIA_CONNECTION_STRING`` — async MySQL/MariaDB URL

The explicit async driver scheme is the canonical form (``postgresql+asyncpg``,
``mysql+aiomysql``), but a plain scheme copied from a client or a DSN doc
(``postgresql://``, ``postgres://``, ``mysql://``, ``mariadb://``) is accepted
as an **alias**. An engine has exactly one supported async driver, so the plain
scheme is unambiguous: it is rewritten at the string level to the canonical
scheme, leaving every byte after ``://`` untouched. This is a spelling fix, not
a driver choice.

An absent or blank variable means "engine not configured": the engine is left
out of the registry and the server keeps booting. A *present* variable is
validated eagerly — the URL must parse and its scheme must be a canonical scheme
or an accepted alias — because a silent misconfiguration here becomes a
confusing driver error much later, far from the cause.

A connection string is a secret. Its value is never echoed in a validation
error, a log line, or a docstring; the messages name the *variable*, never the
value.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Mapping

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from .db_context_options import (
    DEFAULT_POOL_TIMEOUT_SECONDS,
    ENV_CONNECT_TIMEOUT_SECONDS,
    ENV_ECHO,
    ENV_POOL_TIMEOUT_SECONDS,
    ConnectionOptions,
    env_bool,
    env_float,
    env_optional_float,
)
from .supported_engine import SupportedEngine

logger = logging.getLogger(__name__)

# Every connection variable we know ends with this suffix. Scanning for it is
# how a misspelled variable (say ``MYSQL_CONNECTION_STRING``) is detected
# instead of being silently ignored forever.
_CONNECTION_STRING_SUFFIX = "_CONNECTION_STRING"


class ConnectionRegistry(Mapping[SupportedEngine, ConnectionOptions]):
    """Immutable view of which engines are configured and how to reach them.

    The registry is a read-only ``Mapping``: the only way to build one is
    :meth:`from_env`, so no caller can mutate the connection contract behind
    the dispatcher's back. An empty registry is a first-class, valid state —
    "no database configured" must not stop the server from booting.
    """

    def __init__(self, connections: Mapping[SupportedEngine, ConnectionOptions]) -> None:
        """Store a private copy of ``connections``.

        Args:
            connections: Mapping of configured engine to its options.
        """
        # Copy into a plain dict so later mutation of the caller's mapping
        # cannot leak into the registry after construction.
        self._connections: dict[SupportedEngine, ConnectionOptions] = dict(connections)

    @classmethod
    def from_env(cls) -> "ConnectionRegistry":
        """Build the registry from the process environment.

        For each supported engine, in declaration order, reads its connection
        variable. Unset or blank means "not configured" and the engine is
        skipped; a set variable is validated and turned into
        :class:`ConnectionOptions`. Shared knobs (pool timeout, connect timeout,
        echo) apply to every configured connection.

        Returns:
            A registry holding every configured engine (possibly none).

        Raises:
            ValueError: when a set connection variable is unparseable or its
                scheme does not match the engine. Failing here beats a cryptic
                driver error later.
        """
        known = SupportedEngine.env_vars()
        cls._warn_on_unknown_variables(known)

        connections: dict[SupportedEngine, ConnectionOptions] = {}
        for engine in SupportedEngine:
            raw = os.environ.get(engine.env_var)
            if raw is None or not raw.strip():
                # Blank behaves like unset: ``VAR=`` is a common way to clear a
                # value without deleting it, and it must not read as configured.
                continue
            connections[engine] = cls._build_options(engine, raw)
        return cls(connections)

    @staticmethod
    def _warn_on_unknown_variables(known: tuple[str, ...]) -> None:
        """Warn about ``*_CONNECTION_STRING`` variables that match no engine.

        A variable we do not recognize is very likely a typo (a wrong engine
        name, a stray prefix). It is ignored rather than trusted, but the
        warning names it so the mistake is visible. Only variable *names* are
        logged: a value could be a secret, and unknown keys are never read.
        """
        unknown = sorted(
            name
            for name in os.environ
            if name.endswith(_CONNECTION_STRING_SUFFIX) and name not in known
        )
        if unknown:
            logger.warning(
                "Ignoring unrecognized connection variable(s): %s. "
                "Known variables: %s.",
                ", ".join(unknown),
                ", ".join(known),
            )

    @classmethod
    def _build_options(cls, engine: SupportedEngine, raw: str) -> ConnectionOptions:
        """Validate ``raw`` against ``engine`` and build its options.

        The value is normalized to the engine's canonical async driver scheme.
        A URL that already uses the canonical scheme is kept byte-for-byte; a
        URL that uses a plain alias scheme is rewritten at the string level so
        the credentials, host, database, and query parameters survive intact.

        Args:
            engine: The engine this variable configures.
            raw: The raw connection URL, already known to be non-blank.

        Returns:
            Validated options for this engine.

        Raises:
            ValueError: when ``raw`` is not a parseable SQLAlchemy URL, or its
                scheme is neither a canonical scheme nor an accepted alias.
        """
        value = raw.strip()

        try:
            url = make_url(value)
        except ArgumentError as exc:
            # Never interpolate ``value`` here: it is a secret. The variable
            # name is enough for a human to find and fix the value.
            raise ValueError(
                f"{engine.env_var} is not a valid SQLAlchemy URL."
            ) from exc

        driver = url.drivername.lower()
        canonical = {scheme.lower() for scheme in engine.url_schemes}
        aliases = {scheme.lower() for scheme in engine.alias_schemes}

        if driver in canonical:
            # Already canonical: keep the caller's bytes untouched.
            connection_string = value
        elif driver in aliases:
            connection_string = cls._rewrite_scheme(engine, value)
        else:
            # ``url.drivername`` (the scheme) is not secret, so it is safe to
            # include; it is exactly the detail that explains the mismatch.
            raise ValueError(
                f"{engine.env_var} must use "
                f"{', '.join(engine.url_schemes)} for {engine.label}, "
                f"or the plain alias "
                f"{', '.join(engine.alias_schemes)} rewritten to it; "
                f"got driver {url.drivername!r}."
            )

        return (
            ConnectionOptions.builder()
            .with_connection_string(connection_string)
            .with_pool_timeout_seconds(
                env_float(ENV_POOL_TIMEOUT_SECONDS, DEFAULT_POOL_TIMEOUT_SECONDS)
            )
            .with_connect_timeout_seconds(env_optional_float(ENV_CONNECT_TIMEOUT_SECONDS))
            .with_echo(env_bool(ENV_ECHO, False))
            .build()
        )

    @staticmethod
    def _rewrite_scheme(engine: SupportedEngine, value: str) -> str:
        """Rewrite ``value``'s scheme to the engine's canonical async scheme.

        Only the scheme is replaced; everything after ``://`` is preserved
        verbatim. The URL is split at the string level, not rebuilt from its
        parsed parts, because re-rendering can re-encode the password.

        Args:
            engine: The engine whose canonical scheme to use.
            value: A stripped connection URL that already parsed.

        Returns:
            The same URL with the engine's canonical async scheme.

        Raises:
            ValueError: when the URL has no ``://`` separator. This is
                unreachable after a successful parse, but a URL we cannot split
                safely is never rebuilt silently.
        """
        _, separator, remainder = value.partition("://")
        if not separator:
            raise ValueError(f"{engine.env_var} is not a valid SQLAlchemy URL.")
        return f"{engine.url_schemes[0]}://{remainder}"

    @property
    def engines(self) -> tuple[SupportedEngine, ...]:
        """Return the configured engines, in declaration order."""
        return tuple(engine for engine in SupportedEngine if engine in self._connections)

    def is_configured(self, engine: SupportedEngine) -> bool:
        """Return whether ``engine`` has a connection configured."""
        return engine in self._connections

    # -- Mapping protocol -------------------------------------------------
    # Implementing these three methods makes the registry a read-only mapping,
    # so callers get ``get``, ``in``, ``keys`` and iteration for free without a
    # mutable surface to poke at.

    def __getitem__(self, engine: SupportedEngine) -> ConnectionOptions:
        return self._connections[engine]

    def __iter__(self) -> Iterator[SupportedEngine]:
        return iter(self.engines)

    def __len__(self) -> int:
        return len(self._connections)
