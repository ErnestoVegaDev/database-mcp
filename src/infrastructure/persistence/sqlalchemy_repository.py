"""Read-only SQLAlchemy Core adapter behind the ``Repository`` port.

This is the concrete persistence implementation the application talks to
through the port: the use cases know ``Repository``, never this class, which is
what lets the same flow run against a mock or a real database (DIP).

Design notes that a reader should not have to rediscover:

* Everything runs inside ``AsyncSession.run_sync``. SQLAlchemy's inspection and
  reflection APIs are synchronous, so the sync work happens on the greenlet the
  async session manages; the async connection is never touched outside it.
* Identifiers and schemas are quoted by SQLAlchemy reflection, and every filter
  value travels through parameter binding. No identifier or value is ever
  interpolated into a SQL string (D2), so none of this is injection-prone.
* Expected failures are values. A missing table, column, schema or row returns
  ``Failure``; only genuine bugs and unforeseen Python errors are allowed to
  raise (see the error-mapping note below).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.exc import NoSuchTableError, SQLAlchemyError

from application.interfaces import Repository
from domain.enums import ColumnType, FilterOperator
from domain.errors import DomainError, NotFoundError
from domain.value_objects import Filter, FilterCriterion, Pagination, Record, ResultSet
from returns.result import Failure, Result, Success

from .column_type_mapping import to_column_type
from .db_context import DbContext

# Module-scoped logger. On the stdio transport stdout carries the JSON-RPC
# stream, so diagnostics must go to the logging handlers (stderr) instead of
# print(); the full driver detail stays here for the operator, never on the wire.
logger = logging.getLogger(__name__)

# The three catalog columns the port contract promises, in a fixed order.
_CATALOG_COLUMNS: dict[str, ColumnType] = {
    "table_schema": ColumnType.TEXT,
    "table_name": ColumnType.TEXT,
    "table_type": ColumnType.TEXT,
}

# SQLite has no schemas. Its single namespace is named "main", and passing an
# explicit schema to its inspector is meaningless, so the adapter ignores any
# explicit value and labels every catalog row with this name (D3).
_SQLITE_SCHEMA_LABEL = "main"
_SQLITE_DIALECT = "sqlite"

# The two table categories the catalog reports. These literals match the mock
# fixture and information_schema.TABLES.TABLE_TYPE naming so the catalog shape
# does not change when the adapter is swapped in (D4).
_BASE_TABLE = "BASE TABLE"
_VIEW = "VIEW"


def _normalize_value(value: Any) -> Any:
    """Return a value with ``Decimal`` widened to ``float``, and all else intact.

    A numeric column is advertised as ``ColumnType.FLOAT`` (the domain enum has
    no decimal member), so the declared type has to be true of the delivered
    value. Widening ``Decimal`` to ``float`` here keeps that promise at the one
    boundary where both types are visible.

    The tradeoff is honest and deliberate: ``float`` is binary floating point,
    so a ``DECIMAL(38, 2)`` value with more significant digits than a double can
    hold may round. Callers who need exact decimals would need a domain type the
    enum does not offer today; until then, FLOAT is the only representable
    choice. Nothing else is converted: booleans, strings, dates and bytes are
    passed through untouched.
    """
    if isinstance(value, Decimal):
        return float(value)
    return value


def _sanitized_message(error: SQLAlchemyError) -> str:
    """Return a client-safe description of a driver-level failure.

    The MCP edge renders this message to the caller, so it must never leak the
    connection string, the URL, credentials, or the raw driver text - any of
    which can end up inside a ``str(error)`` (a failed connection includes the
    DSN, a failed file open includes a path). Only the exception CLASS name is
    exposed, which classifies the failure without disclosing its contents. The
    full, unsanitized exception is logged to stderr by the caller.
    """
    return (
        "The database operation failed inside the SQL driver. "
        f"Details were logged server-side (classifier: {type(error).__name__})."
    )


def _table_not_found(table: str) -> NotFoundError:
    """Build the expected failure for a table that reflection could not resolve."""
    return NotFoundError(
        f"Table '{table}' does not exist", entity="table", key=table
    )


def _column_not_found(table: str, column: str) -> NotFoundError:
    """Build the expected failure for a column absent from the reflected table."""
    return NotFoundError(
        f"Column '{column}' does not exist in table '{table}'",
        entity="column",
        key=column,
    )


def _schema_not_found(schema: str) -> NotFoundError:
    """Build the expected failure for a schema the dialect does not know."""
    return NotFoundError(
        f"Schema '{schema}' does not exist", entity="schema", key=schema
    )


def _criterion_expression(column: Any, criterion: FilterCriterion) -> Any:
    """Translate one domain criterion into a SQLAlchemy Core boolean expression.

    The translation is total over ``FilterOperator``: the enum is closed, so the
    final ``raise`` is unreachable today and exists only so a new member added
    without a rule fails loudly instead of silently dropping the predicate.

    ``FilterCriterion`` guarantees the value shape before this function sees it:
    the value is already a tuple for IN / NOT_IN and already ``None`` for the
    unary operators, so it is passed straight through and never re-validated.
    """
    operator = criterion.operator
    if operator is FilterOperator.EQ:
        return column == criterion.value
    if operator is FilterOperator.NE:
        # NULL is deliberately NOT special-cased. SQL three-valued logic makes
        # ``col != x`` UNKNOWN (hence unmatching) when ``col`` is NULL, which is
        # exactly the mock's documented behavior. Python's ``!=`` would wrongly
        # match a NULL; the database does not. Do not "fix" this later.
        return column != criterion.value
    if operator is FilterOperator.GT:
        return column > criterion.value
    if operator is FilterOperator.GTE:
        return column >= criterion.value
    if operator is FilterOperator.LT:
        return column < criterion.value
    if operator is FilterOperator.LTE:
        return column <= criterion.value
    if operator is FilterOperator.IN:
        return column.in_(criterion.value)
    if operator is FilterOperator.NOT_IN:
        # Same three-valued logic as ``ne``: ``NOT IN`` never matches a NULL row.
        return column.not_in(criterion.value)
    if operator is FilterOperator.LIKE:
        return column.like(criterion.value)
    if operator is FilterOperator.IS_NULL:
        return column.is_(None)
    if operator is FilterOperator.IS_NOT_NULL:
        return column.is_not(None)
    raise ValueError(f"Unhandled filter operator: {operator!r}")


class SqlAlchemyRepository(Repository):
    """Read-only ``Repository`` backed by SQLAlchemy Core, one dialect-agnostic code path.

    Every method reflects what it needs through the ``Inspector`` and Core, so
    the same class serves SQLite, Postgres and SQL Server without a dialect
    switch. The ``DbContext`` supplies pooled, short-lived sessions; this class
    owns no connection lifecycle of its own.
    """

    def __init__(self, context: DbContext) -> None:
        """Store the database context that hands out sessions.

        Args:
            context: Shared engine and session factory. Injected rather than
                constructed here so the composition root owns the single pool.
        """
        self._context = context

    async def get_table_catalog(
        self,
        pagination: Pagination,
        schema: str | None = None,
    ) -> Result[ResultSet, DomainError]:
        """Return one page of the table catalog, ordered by (schema, name).

        Args:
            pagination: 1-based page window.
            schema: Schema to restrict the catalog to; ``None`` resolves to the
                dialect default, and SQLite ignores an explicit value (D3).
        """
        try:
            async with self._context.session() as session:
                return await session.run_sync(self._read_catalog, pagination, schema)
        except SQLAlchemyError as error:
            # A catalog read reflects metadata, so an SQLAlchemyError here is a
            # driver/connection problem rather than a missing table. Log the real
            # exception (stderr) and hand the caller a sanitized failure (D5).
            logger.error("Table catalog read failed.", exc_info=True)
            return Failure(DomainError(_sanitized_message(error)))

    async def get_result_set(
        self,
        pagination: Pagination,
        table: str,
        columns: tuple[str, ...],
        schema: str | None = None,
        filters: Filter = Filter(),
    ) -> Result[ResultSet, DomainError]:
        """Return one page of a table, projected to ``columns``.

        Filtering on a column that is not projected is legitimate, so the
        projected names AND the filtered names are validated against the
        reflected columns. A missing table or column is an expected ``Failure``.
        """
        try:
            async with self._context.session() as session:
                return await session.run_sync(
                    self._read_result_set, pagination, table, columns, schema, filters
                )
        except NoSuchTableError:
            # NoSuchTableError subclasses InvalidRequestError, which subclasses
            # SQLAlchemyError, so this narrower handler MUST come first or the
            # missing table would be misreported as a driver failure. A missing
            # table is an expected outcome, so it is logged at debug (no
            # traceback) instead of error: there is no operator detail to keep.
            logger.debug("Reflection found no table named '%s'.", table)
            return Failure(_table_not_found(table))
        except SQLAlchemyError as error:
            logger.error("Query failed for table '%s'.", table, exc_info=True)
            return Failure(DomainError(_sanitized_message(error)))

    async def get_record_by(
        self,
        table: str,
        key_column: str,
        key_value: object,
        schema: str | None = None,
    ) -> Result[Record, DomainError]:
        """Return the single row whose ``key_column`` equals ``key_value``.

        The returned ``Record`` holds every reflected column, not a projection.
        A missing row is an expected outcome, reported as a ``Failure``.
        """
        try:
            async with self._context.session() as session:
                return await session.run_sync(
                    self._read_record, table, key_column, key_value, schema
                )
        except NoSuchTableError:
            # Same ordering reason as get_result_set: the narrower expected
            # failure wins. Debug-level, no traceback: a missing table is data,
            # not a crash.
            logger.debug("Reflection found no table named '%s'.", table)
            return Failure(_table_not_found(table))
        except SQLAlchemyError as error:
            logger.error("Key lookup failed for table '%s'.", table, exc_info=True)
            return Failure(DomainError(_sanitized_message(error)))

    def _read_catalog(
        self,
        sync_session: Any,
        pagination: Pagination,
        schema: str | None,
    ) -> Result[ResultSet, DomainError]:
        """Sync callback: reflect the catalog and window one page of it.

        Runs inside ``run_sync``, which hands the callback the SYNC ``Session``
        (not a ``Connection``). The session's own connection is borrowed for
        reflection so the work stays inside the async session's transaction.
        """
        connection = sync_session.connection()
        inspector = inspect(connection)
        resolution = self._resolve_schema(inspector, connection.dialect.name, schema)
        if isinstance(resolution, Failure):
            return Failure(resolution.failure())
        query_schema, label = resolution.unwrap()

        # Combine tables and views, then sort by (schema, name) so the window is
        # deterministic. Without an explicit order, two pages could overlap or
        # skip rows because the database owes no stable order to LIMIT/OFFSET.
        rows: list[tuple[str, str, str]] = [
            (label, name, _BASE_TABLE)
            for name in inspector.get_table_names(schema=query_schema)
        ]
        rows.extend(
            (label, name, _VIEW)
            for name in inspector.get_view_names(schema=query_schema)
        )
        rows.sort(key=lambda row: (row[0], row[1]))

        window = rows[pagination.offset : pagination.offset + pagination.page_size]
        records = tuple(
            Record({"table_schema": s, "table_name": n, "table_type": t})
            for s, n, t in window
        )
        return Success(ResultSet(_CATALOG_COLUMNS, records))

    def _read_result_set(
        self,
        sync_session: Any,
        pagination: Pagination,
        table: str,
        columns: tuple[str, ...],
        schema: str | None,
        filters: Filter,
    ) -> Result[ResultSet, DomainError]:
        """Sync callback: reflect, validate, filter, order, and window one page.

        Raises ``NoSuchTableError`` when the table cannot be reflected; the async
        caller maps that to a ``NotFoundError``. Everything else the caller can
        anticipate (unknown schema or column) is returned as a ``Failure`` value
        right here.
        """
        connection = sync_session.connection()
        inspector = inspect(connection)
        resolution = self._resolve_schema(inspector, connection.dialect.name, schema)
        if isinstance(resolution, Failure):
            return Failure(resolution.failure())
        query_schema, _ = resolution.unwrap()

        # A fresh MetaData per call reflects the live table shape. There is no
        # cache on purpose: a schema that changes underneath the server would
        # otherwise be served stale until restart.
        table_object = Table(
            table, MetaData(), schema=query_schema, autoload_with=connection
        )

        # Projection and filtering both name columns, and a filter may target a
        # column that is not projected, so BOTH sets are validated. Names come
        # from the reflected object, which the dialect already quoted.
        for name in (*columns, *(criterion.column for criterion in filters.criteria)):
            if name not in table_object.columns:
                return Failure(_column_not_found(table, name))

        statement = select(*(table_object.c[name] for name in columns))
        for criterion in filters.criteria:
            statement = statement.where(
                _criterion_expression(table_object.c[criterion.column], criterion)
            )

        # LIMIT/OFFSET without ORDER BY lets the database return the same row on
        # two different pages. The reflected primary key is the natural stable
        # order; when the table has none, no order is imposed and page stability
        # becomes the caller's risk (a keyless table has no stable identity).
        primary_key = list(table_object.primary_key.columns)
        if primary_key:
            statement = statement.order_by(*(column for column in primary_key))

        statement = statement.limit(pagination.page_size).offset(pagination.offset)
        result_rows = connection.execute(statement).all()

        projected = {
            name: to_column_type(table_object.c[name].type) for name in columns
        }
        records = tuple(
            Record(dict(zip(columns, (_normalize_value(value) for value in row))))
            for row in result_rows
        )
        return Success(ResultSet(projected, records))

    def _read_record(
        self,
        sync_session: Any,
        table: str,
        key_column: str,
        key_value: object,
        schema: str | None,
    ) -> Result[Record, DomainError]:
        """Sync callback: reflect, look up one row by key, and widen its values."""
        connection = sync_session.connection()
        inspector = inspect(connection)
        resolution = self._resolve_schema(inspector, connection.dialect.name, schema)
        if isinstance(resolution, Failure):
            return Failure(resolution.failure())
        query_schema, _ = resolution.unwrap()

        table_object = Table(
            table, MetaData(), schema=query_schema, autoload_with=connection
        )

        if key_column not in table_object.columns:
            return Failure(_column_not_found(table, key_column))

        statement = select(table_object).where(
            table_object.c[key_column] == key_value
        )
        row = connection.execute(statement).mappings().first()
        if row is None:
            # A well-formed lookup that matched nothing is an expected outcome,
            # not a crash: the caller asked for a row that is not there.
            return Failure(
                NotFoundError(
                    f"No row in '{table}' with {key_column} = {key_value!r}",
                    entity="row",
                    key=str(key_value),
                )
            )

        values = {
            name: _normalize_value(row[name]) for name in table_object.columns.keys()
        }
        return Success(Record(values))

    def _resolve_schema(
        self,
        inspector: Any,
        dialect_name: str,
        schema: str | None,
    ) -> Result[tuple[str | None, str | None], DomainError]:
        """Resolve the schema to query and the label the catalog should report.

        Returns ``Success((query_schema, label))`` or, for an explicit schema
        the dialect does not know, ``Failure(NotFoundError)``. Modelling the
        "missing schema" case as a ``Failure`` (instead of an in-band ``None``)
        keeps it distinct from a dialect whose ``default_schema_name`` is itself
        ``None``, which is a legitimate "no schema filter" and not an error.

        The rules implement D3:

        * SQLite has no schemas: an explicit value is ignored, the query schema
          is ``None``, and the reported label is SQLite's only namespace name.
        * Any other dialect with ``schema=None`` uses
          ``Inspector.default_schema_name`` (public in Postgres, dbo in SQL
          Server), which is also the label.
        * An explicit schema is honored after being checked against
          ``get_schema_names``; an unknown one is a ``Failure``.
        """
        if dialect_name == _SQLITE_DIALECT:
            # SQLite ignores an explicit schema by design; its one namespace is
            # reached by passing schema=None to the inspector.
            return Success((None, _SQLITE_SCHEMA_LABEL))

        if schema is not None:
            if schema not in inspector.get_schema_names():
                return Failure(_schema_not_found(schema))
            return Success((schema, schema))

        default_schema = inspector.default_schema_name
        return Success((default_schema, default_schema))
