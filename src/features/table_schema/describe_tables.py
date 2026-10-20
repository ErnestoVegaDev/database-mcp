"""Slice: describe_tables — table structures.

Before the model writes a join or projects a column in raw SQL it needs to
know what the table actually contains. This tool answers that with catalog
introspection: the SQL is authored by the server (see ``structure.py``),
never by the caller, so the read-only guard does not apply — there is no
untrusted statement to guard.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import MCPServer
from returns.result import Failure
from sqlalchemy import bindparam, text

from shared.domain.errors import (
    DomainError,
    ValidationError,
    ValidationErrors,
    error_payload,
)
from shared.persistence import DbContextFactory, SupportedEngine

from .structure import fold_tables, structure_queries

# Diagnostics go to logging (stderr), never to print(): on the stdio
# transport stdout carries the JSON-RPC stream.
logger = logging.getLogger(__name__)


class TableSchemaTools:
    """MCP tool group for table structure discovery.

    The group owns exactly one tool today (``describe_tables``); keeping
    the group shape means the composition root registers every slice the
    same way.
    """

    def __init__(self, factory: DbContextFactory) -> None:
        # The factory is the composition root's single handle on persistence:
        # it already knows which engines the environment configured, so this
        # slice never reads os.environ itself.
        self._factory = factory

    def register(self, mcp: MCPServer) -> None:
        """Register this group's tools on the MCP server."""
        mcp.add_tool(self.describe_tables)

    async def describe_tables(
        self,
        engine: str,
        tables: list[str],
        schema: str | None = None,
    ) -> dict[str, Any]:
        """Describe the structure of one or more tables.

        Use this after ``list_database_objects`` and before writing SQL: it
        reports each table's columns (type, nullability, default, primary
        key) and foreign keys, so a query can reference real columns and
        join on real key pairs. The introspection is done by the server
        against the engine's catalog; the caller never supplies SQL.

        Table names are matched EXACTLY — no case folding, no trimming.
        Take them from ``list_database_objects``; a name spelled any other
        way is simply not found (it lands in ``missing``).

        Args:
            engine: Which engine to inspect — one of the supported engine
                names reported by ``list_connections`` (e.g. ``"postgres"``,
                ``"maria"``). An unknown name is a validation error.
            tables: Non-empty list of exact table names to describe.
                Duplicate names are collapsed to one entry. An empty list,
                or any blank or non-string entry, is a validation error.
            schema: Scope to a single schema (PostgreSQL) or a single
                database (MariaDB). None means the engine's current
                default scope: ``current_schema()`` on PostgreSQL,
                ``DATABASE()`` on MariaDB. A scope that does not exist
                resolves every requested name to ``missing`` rather than
                failing.

        Returns:
            On success::

                {
                    "status": "ok",
                    "engine": "postgres",
                    "schema": "public",
                    "tables": [
                        {
                            "name": "orders",
                            "columns": [
                                {"name": "id", "type": "integer",
                                 "nullable": false, "default": null,
                                 "primary_key": true},
                                {"name": "note",
                                 "type": "character varying(50)",
                                 "nullable": true, "default": null,
                                 "primary_key": false}
                            ],
                            "foreign_keys": [
                                {"name": "orders_user_fk",
                                 "columns": ["user_id"],
                                 "referenced_table": "users",
                                 "referenced_columns": ["id"]}
                            ]
                        }
                    ],
                    "missing": ["ordrs"]
                }

            ``schema`` echoes the scope actually used — a resolved default
            such as ``"public"``, never the raw ``null`` input.
            ``tables`` carries every requested name that resolved, IN THE
            ORDER REQUESTED; within a table, ``columns`` is ordered by the
            table's own ordinal position and ``foreign_keys`` by
            constraint name, then column ordinal. ``type`` is composed
            from ``information_schema`` (e.g. ``character varying(50)``,
            ``numeric(12,2)``, plain ``integer``). Composite foreign keys
            pair ``columns`` with ``referenced_columns`` positionally.

            Partial success is explicit: a requested name that cannot be
            found in the scope lands in ``missing`` (in the order
            requested, ``[]`` when none) — one typo never fails the whole
            batch.

            Errors use the envelope ``{"status": "error", "error": {...}}``
            and are returned as values, never raised:

            * an unknown ``engine``, an empty ``tables`` list, or a blank /
              non-string entry is a validation error;
            * a supported but unconfigured engine is a not-found error
              ("not configured");
            * a driver or database failure is sanitized: the payload
              carries only the exception class name, while the full
              traceback goes to the server's stderr. No connection string
              ever appears.
        """
        # Order matters: validate the caller's input first, then resolve
        # the engine — an invalid name must not even hint at configuration
        # state.
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

        if not isinstance(tables, list) or not tables:
            return error_payload(
                ValidationError(
                    "tables must be a non-empty list of exact table names.",
                    field="tables",
                )
            )

        # Invalid entries are collected instead of failing on the first
        # one, so one round trip fixes them all. Entries are checked by
        # index (not value) because a non-string entry may not be
        # hashable. Values are kept as given afterwards: exact-name
        # matching must not trim what the caller sent.
        invalid = tuple(
            ValidationError(
                f"tables[{index}] must be a non-empty string.",
                field="tables",
            )
            for index, value in enumerate(tables)
            if not isinstance(value, str) or not value.strip()
        )
        if invalid:
            return error_payload(
                ValidationErrors(
                    "Invalid tables list.",
                    errors=invalid,
                )
            )

        # Collapse duplicates while preserving request order: one name
        # describes one table, however often it was asked for.
        requested = list(dict.fromkeys(tables))

        result = self._factory.get(engine_enum)
        if isinstance(result, Failure):
            # An unconfigured engine is an expected outcome, not a crash:
            # the factory already shaped it into a renderable domain error.
            return error_payload(result.failure())
        db_context = result.unwrap()

        try:
            queries = structure_queries(engine_enum)
            async with db_context.session() as session:
                # One tiny statement resolves the scope actually in effect
                # so the payload echoes it; NULL means the engine has no
                # current default at all (e.g. no DATABASE() selected).
                scope_row = (
                    await session.execute(
                        text(queries.scope_sql),
                        {"schema": schema},
                    )
                ).one()
                used_scope = (
                    None
                    if scope_row.used_scope is None
                    else str(scope_row.used_scope)
                )
                # Each statement gets its own expanding bindparam: a
                # BindParameter is stateful once bound, so sharing one
                # across two clauses would be asking for trouble.
                column_rows = (
                    await session.execute(
                        text(queries.columns_sql).bindparams(
                            bindparam("names", expanding=True)
                        ),
                        {"schema": schema, "names": requested},
                    )
                ).all()
                constraint_rows = (
                    await session.execute(
                        text(queries.constraints_sql).bindparams(
                            bindparam("names", expanding=True)
                        ),
                        {"schema": schema, "names": requested},
                    )
                ).all()
        except Exception as exc:
            # A driver or database failure. The full traceback goes to
            # stderr (a driver error message can embed the DSN), and the
            # payload — which may reach the client — carries only the
            # exception CLASS name, never the message.
            logger.error(
                "Failed to describe tables for %s.",
                engine_enum.label,
                exc_info=True,
            )
            return error_payload(
                DomainError(
                    f"Failed to describe tables for "
                    f"{engine_enum.value!r}: {type(exc).__name__}."
                )
            )

        tables_payload, missing = fold_tables(
            requested, column_rows, constraint_rows
        )

        return {
            "status": "ok",
            "engine": engine_enum.value,
            "schema": used_scope,
            "tables": tables_payload,
            "missing": missing,
        }
