"""Async SQLAlchemy engine and session lifecycle.

This module lives in the infrastructure layer. Infrastructure is the only
layer allowed to know about concrete tools such as SQLAlchemy: the domain and
application layers talk to a ``Repository`` interface, and a concrete
implementation of that interface is the one that uses the ``DbContext``
defined here.
"""

# ``from __future__ import annotations`` turns every annotation into a lazy
# string instead of evaluating it at import time. Two practical wins here:
#   1. Modern syntax like ``AsyncIterator[AsyncSession]`` works everywhere.
#   2. Importing this module does not eagerly resolve the SQLAlchemy types.
from __future__ import annotations

# PEP 8 import order: standard library first, then third-party, then local.
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.util import get_cls_kwargs

from .db_context_options import DbContextOptions


def _pool_supports_timeout(connection_string: str) -> bool:
    """Return whether the pool SQLAlchemy picks for this URL accepts a timeout.

    SQLAlchemy maps the public ``pool_timeout`` engine argument onto the pool's
    own ``timeout`` parameter and rejects it for pools that have no queue. An
    in-memory SQLite URL selects ``StaticPool``, and ``NullPool`` has no queue
    either: forwarding ``pool_timeout`` there raises ``TypeError``. Resolving
    the pool class up front lets the engine be built with only the knobs that
    pool actually understands.
    """
    url = make_url(connection_string)
    pool_class = url.get_dialect().get_pool_class(url)
    return "timeout" in get_cls_kwargs(pool_class)


class DbContext:
    """Own one async engine and hand out short-lived sessions.

    Think of this class as the single door to the database for the whole
    process:

    * The ``engine`` is the connection pool. Build it once and share it.
    * A ``session`` is a short-lived unit of work (one query, or one
      transaction). Ask for one per operation and let it close.

    Creating one instance per process avoids opening a brand-new pool on every
    request, which is what makes a shared engine worth having.
    """

    def __init__(self, options: DbContextOptions) -> None:
        """Build the engine and the session factory from ``options``.

        Args:
            options: Immutable, already-validated configuration. Build it with
                ``DbContextOptions.builder()`` or ``DbContextOptions.from_env()``.
        """
        # Keep the options for diagnostics and for future knobs.
        self._options = options

        # Driver-specific connect timeout. SQLAlchemy forwards connect_args to
        # the DBAPI/driver. asyncpg and pyodbc (aioodbc) both accept "timeout";
        # aiosqlite ignores it, so when it is unset we send nothing at all.
        connect_args: dict[str, object] = {}
        if options.connect_timeout_seconds is not None:
            connect_args["timeout"] = options.connect_timeout_seconds

        # Pool knobs are driver-agnostic, but not every pool is a queue. Only
        # forward pool_timeout when the resolved pool class supports it, so an
        # in-memory SQLite URL (StaticPool) does not blow up engine creation.
        pool_kwargs: dict[str, object] = {
            # pool_pre_ping discards connections the server already closed, so
            # intermittent "connection closed" errors become a silent reconnect.
            "pool_pre_ping": True,
        }
        if _pool_supports_timeout(options.connection_string):
            # Driver-agnostic: SQLAlchemy enforces how long a caller waits for
            # a free pooled connection.
            pool_kwargs["pool_timeout"] = options.pool_timeout_seconds

        # The engine is the pool, not a single connection. Creating it does NOT
        # connect yet: the first real connection happens on the first query.
        # That is why building it outside a running event loop is safe.
        self._engine: AsyncEngine = create_async_engine(
            options.connection_string,
            # echo=True logs every SQL statement; keep it off in production.
            echo=options.echo,
            connect_args=connect_args,
            **pool_kwargs,
        )

        # The session factory is a callable that produces AsyncSession objects
        # bound to the engine's pool. Keeping one factory (instead of building
        # a sessionmaker per request) keeps the configuration in one place.
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            # ``class_`` is the session type to instantiate. The trailing
            # underscore avoids clashing with the ``class`` keyword.
            class_=AsyncSession,
            # expire_on_commit=False is REQUIRED for async usage. With the
            # default (True), objects are expired after commit and reading an
            # attribute triggers an implicit lazy-load, which raises
            # MissingGreenlet on an async engine.
            expire_on_commit=False,
            # autoflush=False stops SQLAlchemy from flushing pending changes
            # implicitly before every query. Explicit flushes are easier to
            # reason about, especially in a read-oriented server like this one.
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        """Return the shared engine (for metadata, DDL, or health checks)."""
        # Exposed read-only through a property: callers can inspect the engine
        # but cannot replace it and desynchronize it from the session factory.
        return self._engine

    @property
    def options(self) -> DbContextOptions:
        """Return the immutable options this context was built from."""
        return self._options

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session bound to this context, then always close it.

        Usage::

            async with db_context.session() as session:
                result = await session.execute(...)

        The session is closed no matter what, so it can never leak back into
        the pool.
        """
        # The sessionmaker's own context manager closes the session in a
        # ``finally``; that is what guarantees the session is released even if
        # the caller's body raises.
        async with self._session_factory() as session:
            try:
                # Hand control to the caller: the code inside their ``async
                # with`` block runs here.
                yield session
            except Exception:
                # On any error, roll back so the session is left clean before
                # it is closed. Without this, a half-applied transaction could
                # stay pending until close.
                await session.rollback()
                # Re-raise: the caller must still see the original error.
                raise

    async def dispose(self) -> None:
        """Close pooled connections and release the engine.

        Call this on application shutdown so the process does not leave
        connections hanging on the database server.
        """
        await self._engine.dispose()
