"""The one place that turns a configured engine into a live DbContext.

Everything that needs to talk to the database asks this factory for the context
of a named engine. Centralizing construction buys two things:

* **One pool per engine per process.** The factory caches the context it
  builds, so repeated calls share a single pooled engine instead of opening a
  new pool on every request.
* **Expected failures stay values.** Asking for an engine that is not
  configured is a normal outcome, not a bug, so it comes back as a ``Failure``
  carrying a :class:`NotFoundError`, ready to be rendered by the MCP edge. A
  genuine creation failure is sanitized the same way instead of raising.

A creation failure is *not* cached: a temporarily missing driver should be
retried on the next call, and each attempt reports cleanly.
"""

from __future__ import annotations

import logging

from returns.result import Failure, Result, Success

from shared.domain.errors import DomainError, NotFoundError

from .connection_registry import ConnectionRegistry
from .db_context import DbContext
from .supported_engine import SupportedEngine

logger = logging.getLogger(__name__)


class DbContextFactory:
    """Dispatch engines to cached :class:`DbContext` instances.

    Build one per process and share it: it holds the cache that keeps a single
    pooled engine alive per configured engine.
    """

    def __init__(self, registry: ConnectionRegistry) -> None:
        """Store the registry and start with an empty context cache.

        Args:
            registry: The configured connections to dispatch from.
        """
        self._registry = registry
        self._contexts: dict[SupportedEngine, DbContext] = {}

    def get(self, engine: SupportedEngine) -> Result[DbContext, DomainError]:
        """Return the context for ``engine``, building and caching it once.

        Args:
            engine: The engine to get a context for.

        Returns:
            ``Success`` holding the shared context; ``Failure`` holding a
            :class:`NotFoundError` when the engine is not configured, or a
            :class:`DomainError` when the context could not be created.
        """
        cached = self._contexts.get(engine)
        if cached is not None:
            return Success(cached)

        options = self._registry.get(engine)
        if options is None:
            # Not configured is an expected outcome, not an error: the caller
            # (an MCP tool) renders this as a structured "not configured" reply.
            return Failure(
                NotFoundError(
                    f"Engine {str(engine)!r} is not configured.",
                    entity="connection",
                    key=str(engine),
                )
            )

        try:
            context = DbContext(options)
        except Exception as exc:
            # A driver import failure (NoSuchModuleError), a URL the scheme
            # check let through, and so on. Log the full traceback to stderr,
            # but return only the exception CLASS name: a driver error message
            # can embed the DSN, and a failure value may reach a tool response.
            logger.error(
                "Failed to create a database context for %s.",
                engine.label,
                exc_info=True,
            )
            return Failure(
                DomainError(
                    f"Failed to create a database context for "
                    f"{str(engine)!r}: {type(exc).__name__}."
                )
            )

        self._contexts[engine] = context
        return Success(context)

    @property
    def configured_engines(self) -> tuple[SupportedEngine, ...]:
        """Return the engines that have a connection configured."""
        return self._registry.engines

    def is_configured(self, engine: SupportedEngine) -> bool:
        """Return whether ``engine`` has a connection configured."""
        return self._registry.is_configured(engine)

    async def dispose_all(self) -> None:
        """Dispose every cached context, then clear the cache.

        Called on shutdown. A context that fails to dispose is logged and
        skipped so the remaining contexts still get their chance to close.
        """
        for context in tuple(self._contexts.values()):
            try:
                await context.dispose()
            except Exception:
                # Shutdown must be best-effort: one stuck pool must not strand
                # the others. The traceback goes to stderr for diagnosis.
                logger.error(
                    "Failed to dispose a database context during shutdown.",
                    exc_info=True,
                )
        self._contexts.clear()
