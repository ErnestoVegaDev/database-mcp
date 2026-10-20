"""Slice: get_database_info — engine type, version, and features.

Before the model writes raw SQL against a configured engine it needs to know
what that engine *is* and which language features it supports. This tool
answers that with one server-authored statement per engine (see
``capabilities.py``): the SQL is fixed here, never supplied by the caller, so
the read-only guard does not apply — there is no untrusted statement to
guard.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import MCPServer
from returns.result import Failure
from sqlalchemy import text

from shared.domain.errors import DomainError, ValidationError, error_payload
from shared.persistence import DbContextFactory, SupportedEngine

from .capabilities import (
    MARIA_INFO_SQL,
    POSTGRES_INFO_SQL,
    build_maria_features,
    build_postgres_features,
    parse_version,
    strip_maria_shim,
)

# Diagnostics go to logging (stderr), never to print(): on the stdio transport
# stdout carries the JSON-RPC stream.
logger = logging.getLogger(__name__)


class DatabaseInfoTools:
    """MCP tool group for engine capability discovery.

    The group owns exactly one tool today (``get_database_info``); keeping
    the group shape means the composition root registers every slice the same
    way.
    """

    def __init__(self, factory: DbContextFactory) -> None:
        # The factory is the composition root's single handle on persistence:
        # it already knows which engines the environment configured, so this
        # slice never reads os.environ itself.
        self._factory = factory

    def register(self, mcp: MCPServer) -> None:
        """Register this group's tools on the MCP server."""
        mcp.add_tool(self.get_database_info)

    async def get_database_info(self, engine: str) -> dict[str, Any]:
        """Report an engine's type, version, feature matrix, and extensions.

        Use this before writing SQL against an engine: it tells you which
        version you are talking to and which language features (CTEs, window
        functions, upserts, ...) the server actually supports.

        Args:
            engine: Which engine to inspect — one of the supported engine
                names reported by ``list_connections`` (e.g. ``"postgres"``,
                ``"maria"``). An unknown name is a validation error.

        Returns:
            On success::

                {
                    "status": "ok",
                    "engine": "postgres",
                    "type": "PostgreSQL",
                    "version": {
                        "raw": "16.4", "major": 16, "minor": 4, "patch": null
                    },
                    "features": {
                        "procedures": true, "cte": true,
                        "recursive_cte": true, "window_functions": true,
                        "json": true, "returning": true, "upsert": true
                    },
                    "extensions": ["plpgsql", "pg_stat_statements"]
                }

            ``type`` is the server's own catalog label for the engine — it is
            never queried from the database. ``version.raw`` is the version
            string exactly as the server reported it (including MariaDB's
            ``5.5.5-`` compatibility prefix, if any); ``major``/``minor``/
            ``patch`` are its parsed numeric parts, ``null`` when a part is
            absent (``16.4`` has no patch, ``17beta1`` has no minor) or the
            string could not be parsed at all.

            ``features`` always carries exactly these seven keys, in order:
            ``procedures``, ``cte``, ``recursive_cte``, ``window_functions``,
            ``json``, ``returning``, ``upsert``. A value of ``null`` means
            the version could not be determined, so the capability is
            UNKNOWN — never read ``null`` as ``false``.

            ``extensions`` lists the installed PostgreSQL extensions; it is
            always ``[]`` on MariaDB, which has no equivalent catalog.

            Errors use the envelope ``{"status": "error", "error": {...}}``
            and are returned as values, never raised:

            * an unknown ``engine`` is a validation error whose message
              lists the allowed values;
            * a supported but unconfigured engine is a not-found error
              ("not configured");
            * a driver or database failure is sanitized: the payload carries
              only the exception class name, while the full traceback goes to
              the server's stderr. No connection string ever appears.
        """
        # Order matters: validate the caller's input first, then resolve the
        # engine — an invalid name must not even hint at configuration state.
        try:
            engine_enum = SupportedEngine(engine)
        except ValueError:
            allowed = ", ".join(repr(value) for value in SupportedEngine)
            return error_payload(
                ValidationError(
                    f"Unknown engine {engine!r}. Allowed values: {allowed}.",
                    field="engine",
                )
            )

        result = self._factory.get(engine_enum)
        if isinstance(result, Failure):
            # An unconfigured engine is an expected outcome, not a crash: the
            # factory already shaped it into a renderable domain error.
            return error_payload(result.failure())
        db_context = result.unwrap()

        try:
            # One statement, one round trip: both engines report everything
            # the payload needs from a single row.
            async with db_context.session() as session:
                if engine_enum is SupportedEngine.POSTGRES:
                    row = (await session.execute(text(POSTGRES_INFO_SQL))).one()
                    # Echo the server's string verbatim; parsing runs on the
                    # raw string (PostgreSQL has no prefix to strip).
                    raw = str(row.raw)
                    version = parse_version(raw)
                    features = build_postgres_features(version, row.num)
                    # array_agg returns NULL for zero extensions; widen the
                    # names at the slice edge so the payload stays JSON-safe.
                    extensions = (
                        []
                        if row.extensions is None
                        else [str(name) for name in row.extensions]
                    )
                elif engine_enum is SupportedEngine.MARIA:
                    row = (await session.execute(text(MARIA_INFO_SQL))).one()
                    raw = str(row.raw)
                    # Strip the 5.5.5- replication-compatibility shim only
                    # for parsing; ``raw`` still echoes what the server sent.
                    version = parse_version(strip_maria_shim(raw), raw=raw)
                    features = build_maria_features(version)
                    # MariaDB has no catalog of installed components
                    # equivalent to pg_extension, so the list is empty by
                    # design — an honest [], never a guessed inventory.
                    extensions = []
                else:
                    # Unreachable while SupportedEngine has exactly the two
                    # engines handled above; a new engine must bring its
                    # info query along.
                    raise ValueError(
                        f"No database info query defined for engine "
                        f"{engine_enum.value!r}."
                    )
        except Exception as exc:
            # A driver or database failure. The full traceback goes to stderr
            # (a driver error message can embed the DSN), and the payload —
            # which may reach the client — carries only the exception CLASS
            # name, never the message.
            logger.error(
                "Failed to get database info for %s.",
                engine_enum.label,
                exc_info=True,
            )
            return error_payload(
                DomainError(
                    f"Failed to get database info for "
                    f"{engine_enum.value!r}: {type(exc).__name__}."
                )
            )

        return {
            "status": "ok",
            "engine": engine_enum.value,
            "type": engine_enum.label,
            "version": version,
            "features": features,
            "extensions": extensions,
        }
