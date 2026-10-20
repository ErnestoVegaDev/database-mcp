"""Slice: list_database_objects — discover tables, views, and routines.

Before the model can write raw SQL against a configured engine it needs to know
what that engine contains. This tool answers that question with catalog
introspection: the SQL is authored by the server (see ``catalog.py``), never by
the caller, so the read-only guard does not apply — there is no untrusted
statement to guard.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import MCPServer
from returns.result import Failure
from sqlalchemy import text
from sqlalchemy.engine import Row

from shared.domain.errors import (
    DomainError,
    ValidationError,
    ValidationErrors,
    error_payload,
)
from shared.persistence import DbContextFactory, SupportedEngine

from .catalog import KINDS, CatalogQuery, catalog_queries

# Diagnostics go to logging (stderr), never to print(): on the stdio transport
# stdout carries the JSON-RPC stream.
logger = logging.getLogger(__name__)


def _serialize_row(query: CatalogQuery, row: Row) -> dict[str, Any] | None:
    """Map one catalog row to a JSON-safe object entry, or None to skip it.

    A catalog type the query's ``kind_map`` does not know is skipped: the
    reported kind must stay a reliable guide for the SQL the model writes
    next, so guessing is worse than omitting.

    Schema and name are widened with ``str`` at the slice edge: the MCP layer
    can only serialize plain Python types, and drivers have opinions about
    string-ish column types.
    """
    kind = query.kind_map.get(getattr(row, query.type_column))
    if kind is None:
        return None
    return {
        "kind": kind,
        "schema": str(getattr(row, query.schema_column)),
        "name": str(getattr(row, query.name_column)),
    }


class DatabaseObjectsTools:
    """MCP tool group for schema discovery.

    The group owns exactly one tool today (``list_database_objects``); keeping
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
        mcp.add_tool(self.list_database_objects)

    async def list_database_objects(
        self,
        engine: str,
        kinds: list[str] | None = None,
        schema: str | None = None,
    ) -> dict[str, Any]:
        """List the tables, views, procedures, and functions of an engine.

        Use this before writing any SQL: it reports what objects exist so a
        query can name real schemas and objects. The introspection is done by
        the server against the engine's catalog; the caller never supplies SQL.

        Args:
            engine: Which engine to inspect — one of the supported engine
                names reported by ``list_connections`` (e.g. ``"postgres"``,
                ``"maria"``). An unknown name is a validation error.
            kinds: Restrict the answer to a subset of ``"table"``, ``"view"``,
                ``"procedure"``, ``"function"``. None or an empty list means
                every kind; any other value is a validation error naming the
                allowed values.
            schema: Scope to a single schema (PostgreSQL) or a single database
                (MariaDB). None means the engine's default scope: every
                non-system schema on PostgreSQL, the current database on
                MariaDB. A schema that does not exist yields an empty list,
                not an error.

        Returns:
            On success::

                {
                    "status": "ok",
                    "engine": "postgres",
                    "objects": [
                        {"kind": "table", "schema": "public", "name": "orders"}
                    ],
                    "counts": {
                        "table": 1, "view": 0, "procedure": 0, "function": 0
                    }
                }

            ``counts`` always carries all four kind keys (zero-filled) and is
            computed after the ``kinds`` filter.

            Errors use the envelope ``{"status": "error", "error": {...}}``
            and are returned as values, never raised:

            * an unknown ``engine`` or an invalid ``kinds`` entry is a
              validation error whose message lists the allowed values;
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

        # None and [] both mean "every kind": the filter only exists when the
        # caller actually narrowed it. Invalid entries are collected instead
        # of failing on the first one, so one round trip fixes them all.
        kind_filter: set[str] | None = None
        if kinds:
            invalid = list(
                dict.fromkeys(kind for kind in kinds if kind not in KINDS)
            )
            if invalid:
                allowed = ", ".join(repr(kind) for kind in KINDS)
                return error_payload(
                    ValidationErrors(
                        "Invalid kinds filter.",
                        errors=tuple(
                            ValidationError(
                                f"Unknown kind {kind!r}. "
                                f"Allowed values: {allowed}.",
                                field="kinds",
                            )
                            for kind in invalid
                        ),
                    )
                )
            kind_filter = set(kinds)

        result = self._factory.get(engine_enum)
        if isinstance(result, Failure):
            # An unconfigured engine is an expected outcome, not a crash: the
            # factory already shaped it into a renderable domain error.
            return error_payload(result.failure())
        db_context = result.unwrap()

        objects: list[dict[str, Any]] = []
        try:
            async with db_context.session() as session:
                for query in catalog_queries(engine_enum, schema):
                    params = {"schema": schema} if query.binds_schema else {}
                    rows = (await session.execute(text(query.sql), params)).all()
                    for row in rows:
                        serialized = _serialize_row(query, row)
                        if serialized is not None:
                            objects.append(serialized)
        except Exception as exc:
            # A driver or database failure. The full traceback goes to stderr
            # (a driver error message can embed the DSN), and the payload —
            # which may reach the client — carries only the exception CLASS
            # name, never the message.
            logger.error(
                "Failed to list database objects for %s.",
                engine_enum.label,
                exc_info=True,
            )
            return error_payload(
                DomainError(
                    f"Failed to list database objects for "
                    f"{engine_enum.value!r}: {type(exc).__name__}."
                )
            )

        # The kinds filter is applied in Python, after fetching: the catalog
        # queries stay static per engine, and filtering can never inject input
        # into SQL.
        if kind_filter is not None:
            objects = [obj for obj in objects if obj["kind"] in kind_filter]

        # Zero-fill from the full vocabulary so the shape does not depend on
        # what the database happened to return.
        counts = {kind: 0 for kind in KINDS}
        for obj in objects:
            counts[obj["kind"]] += 1

        return {
            "status": "ok",
            "engine": engine_enum.value,
            "objects": objects,
            "counts": counts,
        }
