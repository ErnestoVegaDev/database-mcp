"""Slice: execute_query — run one read-only statement and return its rows.

This is the ONLY tool that lets model-authored SQL reach the database, so it
is the only one guarded by ``shared.sql.ensure_read_only`` (decision D3).
Two independent safety layers run in this order, before the driver ever sees
the statement:

1. input validation (engine, sql, max_rows) rendered as D5 error values;
2. the lexical read-only guard — a ``ValidationError`` value stops the call.

A server-side read-only transaction (``_READ_ONLY_TX`` below) is the third,
semantic backstop: even if lexical classification were fooled by a function
with side effects, the database itself refuses writes inside it.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import MCPServer
from returns.result import Failure
from sqlalchemy import text

from shared.domain.errors import DomainError, ValidationError, error_payload
from shared.persistence import DbContextFactory, SupportedEngine
from shared.sql import ensure_read_only

from .row_serialization import to_json_safe

# Diagnostics go to logging (stderr), never to print(): on the stdio
# transport stdout carries the JSON-RPC stream.
logger = logging.getLogger(__name__)

_DEFAULT_MAX_ROWS = 1_000
_MIN_MAX_ROWS = 1
_MAX_MAX_ROWS = 10_000

# The read-only transaction, per engine. ORDERING IS A SAFETY PROPERTY: this
# statement must be the FIRST thing executed in the session, before the
# model's SQL — PostgreSQL's ``SET TRANSACTION READ ONLY`` only applies to
# the current, still-empty transaction, and any real statement would
# implicitly start it unprotected. On MariaDB/MySQL, ``START TRANSACTION
# READ ONLY`` implicitly commits SQLAlchemy's empty autobegin; that commit
# is harmless because the read-only transaction it opens is the one that
# executes the model's SQL. This per-dialect behavior is flagged for LIVE
# verification by the user — the intent is unmistakable in the code: the
# guard statement always runs first, the model's statement always runs
# inside it.
_READ_ONLY_TX: dict[SupportedEngine, str] = {
    SupportedEngine.POSTGRES: "SET TRANSACTION READ ONLY",
    SupportedEngine.MARIA: "START TRANSACTION READ ONLY",
}


class QueryTools:
    """MCP tool group for read-only SQL execution.

    The group owns exactly one tool today (``execute_query``); keeping
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
        mcp.add_tool(self.execute_query)

    async def execute_query(
        self,
        engine: str,
        sql: str,
        max_rows: int = _DEFAULT_MAX_ROWS,
    ) -> dict[str, Any]:
        """Execute ONE read-only SQL statement and return its rows.

        Write the statement yourself; the server classifies it and rejects
        anything that is not read-only (non-``SELECT``/``SHOW``/``WITH``
        starters, DML/DDL keywords anywhere including data-modifying CTEs,
        multiple statements) BEFORE it reaches the database. The statement
        also runs inside a database-side read-only transaction as a second
        line of defense. One statement per call — no semicolons separating
        statements.

        Args:
            engine: Which engine to run the statement on — one of the
                supported engine names reported by ``list_connections``
                (e.g. ``"postgres"``, ``"maria"``). An unknown name is a
                validation error; a supported but unconfigured engine is a
                not-found error.
            sql: The raw statement to execute. Must be non-blank and
                read-only. No bind parameters are supported: raw SQL is the
                contract, so embed literal values directly.
            max_rows: Hard cap on returned rows, 1..10000 (default 1000).
                The statement is asked for at most ``max_rows + 1`` rows, so
                a huge result never materializes in full; out-of-range
                values are a validation error.

        Returns:
            On success::

                {
                    "status": "ok",
                    "engine": "postgres",
                    "columns": ["id", "total"],
                    "rows": [[1, 19.99], [2, 5.0]],
                    "row_count": 2,
                    "truncated": false
                }

            Rows are POSITIONAL: each entry in ``rows`` maps to ``columns``
            by index. Map a row with ``dict(zip(payload["columns"],
            payload["rows"][i]))`` — this pairing survives duplicate column
            aliases (e.g. ``SELECT t1.id, t2.id``), which a dict-shaped row
            would silently collapse. Duplicate names in ``columns`` are
            preserved for the same reason.

            ``truncated`` is true when more rows matched than ``max_rows``:
            the first ``max_rows`` were kept and the rest discarded, and
            ``row_count`` equals ``max_rows``. Narrow with ``LIMIT`` /
            ``WHERE`` and re-query for the rest.

            Values are widened to JSON-safe types at the edge: ``bytes``
            columns arrive base64-encoded, ``Decimal`` columns arrive as
            floats (fine for display, not for exact money arithmetic — cast
            to text in SQL when precision matters), and temporal columns
            arrive as ISO 8601 strings.

            Errors use the envelope ``{"status": "error", "error": {...}}``
            and are returned as values, never raised:

            * an unknown ``engine``, blank ``sql``, or an out-of-range
              ``max_rows`` is a validation error;
            * a statement the read-only guard rejects is a validation error
              naming the offending keyword (never echoing the statement);
            * a supported but unconfigured engine is a not-found error
              ("not configured");
            * a driver or database failure is sanitized: the payload carries
              only the exception class name, while the full traceback goes
              to the server's stderr. No connection string ever appears.
        """
        # Order matters: validate the caller's input first, then resolve
        # the engine — an invalid name must not even hint at configuration
        # state, and an invalid statement must not even open a pool.
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

        if not isinstance(sql, str) or not sql.strip():
            return error_payload(
                ValidationError(
                    "sql must be a non-blank string.",
                    field="sql",
                )
            )

        # bool is a subclass of int; reject it explicitly so True never
        # sneaks through as max_rows=1.
        if (
            not isinstance(max_rows, int)
            or isinstance(max_rows, bool)
            or not _MIN_MAX_ROWS <= max_rows <= _MAX_MAX_ROWS
        ):
            return error_payload(
                ValidationError(
                    f"max_rows must be an integer between "
                    f"{_MIN_MAX_ROWS} and {_MAX_MAX_ROWS}.",
                    field="max_rows",
                )
            )

        # Safety layer 2 of 2: the lexical read-only guard (decision D3).
        # A rejection here means the driver must NEVER see the statement —
        # return immediately, no factory lookup, no session, no SQL.
        guard_error = ensure_read_only(sql)
        if guard_error is not None:
            return error_payload(guard_error)

        result = self._factory.get(engine_enum)
        if isinstance(result, Failure):
            # An unconfigured engine is an expected outcome, not a crash:
            # the factory already shaped it into a renderable domain error.
            return error_payload(result.failure())
        db_context = result.unwrap()

        try:
            read_only_statement = _READ_ONLY_TX[engine_enum]
            async with db_context.session() as session:
                # FIRST statement in the session: open the read-only
                # transaction BEFORE the model's SQL (see _READ_ONLY_TX).
                await session.execute(text(read_only_statement))

                # Raw SQL by design (decision D3): no bind parameters, the
                # statement is executed exactly as the model wrote it.
                query_result = await session.execute(text(sql))
                # Fetch one row beyond the cap: its arrival is what proves
                # the result was truncated, without materializing the rest.
                raw_rows = query_result.fetchmany(max_rows + 1)
                # Column names in result order, duplicates preserved — the
                # payload's positional rows are meaningless without them.
                columns = [str(name) for name in query_result.keys()]
        except Exception as exc:
            # A driver or database failure. The full traceback goes to
            # stderr (a driver error message can embed the DSN), and the
            # payload — which may reach the client — carries only the
            # exception CLASS name, never the message.
            logger.error(
                "Failed to execute query on %s.",
                engine_enum.label,
                exc_info=True,
            )
            return error_payload(
                DomainError(
                    f"Failed to execute query on "
                    f"{engine_enum.value!r}: {type(exc).__name__}."
                )
            )

        truncated = len(raw_rows) > max_rows
        if truncated:
            raw_rows = raw_rows[:max_rows]

        # Serialize at the slice edge: drivers return Decimal/datetime/
        # UUID/bytes, which the MCP layer cannot encode. The mapping is
        # per-cell and positional, so it stays aligned with ``columns``.
        rows = [[to_json_safe(value) for value in row] for row in raw_rows]

        return {
            "status": "ok",
            "engine": engine_enum.value,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
