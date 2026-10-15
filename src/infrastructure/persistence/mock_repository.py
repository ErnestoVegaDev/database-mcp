"""Temporary in-memory Repository used until the SQL adapter exists."""

import re
from typing import Any, Mapping

# Absolute imports from src/: infrastructure may depend on application + domain.
from application.interfaces import Repository
from domain.enums import ColumnType, FilterOperator
from domain.errors import DomainError, NotFoundError, ValidationError
from domain.value_objects import Filter, FilterCriterion, Pagination, Record, ResultSet
from returns.result import Failure, Result, Success

# Schema used when a caller asks for "no schema": Postgres is the flavor this
# stand-in mimics, so its effective default is public.
_DEFAULT_SCHEMA = "public"

# Schemas this stand-in pretends to know; anything else is a NotFoundError.
_KNOWN_SCHEMAS = frozenset({"public", "dbo", "main"})

_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("public", "users", "BASE TABLE"),
    ("public", "orders", "BASE TABLE"),
)

# Canned rows per table, keyed by (schema, table). Each entry pairs the
# column -> ColumnType mapping with the row tuples in that same column order,
# so a table's types, its rows, and the catalog above stay one consistent
# fixture. Row tuples are positional; the mapping supplies the names.
_TABLES: dict[tuple[str, str], tuple[Mapping[str, ColumnType], tuple[tuple, ...]]] = {
    ("public", "users"): (
        {
            "id": ColumnType.INTEGER,
            "name": ColumnType.TEXT,
            "email": ColumnType.TEXT,
            "age": ColumnType.INTEGER,
            "active": ColumnType.BOOLEAN,
        },
        (
            (1, "Ada Lovelace", "ada@example.com", 36, True),
            (2, "Alan Turing", "alan@example.com", 41, True),
            (3, "Grace Hopper", "grace@example.com", 85, False),
            (4, "Anonymous", None, None, False),
        ),
    ),
    ("public", "orders"): (
        {
            "id": ColumnType.INTEGER,
            "user_id": ColumnType.INTEGER,
            "total": ColumnType.FLOAT,
            "status": ColumnType.TEXT,
        },
        (
            (1, 1, 99.5, "paid"),
            (2, 1, 12.0, "pending"),
            (3, 2, 250.75, "paid"),
            (4, 3, 5.0, "cancelled"),
            (5, 4, None, "pending"),
        ),
    ),
}

def _matches_like(value: Any, pattern: str) -> bool:
    """Return whether ``value`` fully matches a SQL LIKE pattern.

    A LIKE pattern is a SQL pattern, not a regex: ``%`` matches any run of
    characters, ``_`` matches exactly one, and every other character is
    literal. Escaping the rest keeps a literal ``.`` or ``*`` from turning into
    a wildcard. ``re.fullmatch`` (case-sensitive, Postgres-flavored) is used
    because Postgres LIKE is case-sensitive by default, so no IGNORECASE flag
    is applied.
    """
    parts: list[str] = []
    for char in pattern:
        if char == "%":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))
    return re.fullmatch("".join(parts), value) is not None


def _matches(row: Mapping[str, Any], criterion: FilterCriterion) -> bool:
    """Return whether one row mapping satisfies one filter criterion.

    SQL three-valued logic: a comparison against NULL is UNKNOWN, so a row
    whose stored value is NULL is excluded rather than raising. This matters
    for ``ne`` and ``not_in``, where Python's ``!=`` / ``not in`` would
    otherwise wrongly match a NULL.
    """
    value = row[criterion.column]
    operator = criterion.operator

    if operator is FilterOperator.IS_NULL:
        return value is None
    if operator is FilterOperator.IS_NOT_NULL:
        return value is not None

    if value is None:
        return False

    if operator is FilterOperator.EQ:
        return value == criterion.value
    if operator is FilterOperator.NE:
        return value != criterion.value
    if operator is FilterOperator.IN:
        return value in criterion.value
    if operator is FilterOperator.NOT_IN:
        return value not in criterion.value
    if operator is FilterOperator.GT:
        return value > criterion.value
    if operator is FilterOperator.GTE:
        return value >= criterion.value
    if operator is FilterOperator.LT:
        return value < criterion.value
    if operator is FilterOperator.LTE:
        return value <= criterion.value
    if operator is FilterOperator.LIKE:
        return _matches_like(value, criterion.value)

    return False


class MockRepository(Repository):
    """Stand-in adapter: canned data behind the real port contract.

    It exercises the full flow -- validation, filtering, projection, and
    pagination -- with no database. Swap it for the SQL adapter and neither the
    use case nor the MCP edge has to change. It deliberately duplicates
    semantics (operator behavior, NULL handling, LIKE translation) that the SQL
    adapter will own for real.
    """

    async def get_table_catalog(
        self,
        pagination: Pagination,
        schema: str | None = None,
    ) -> Result[ResultSet, DomainError]:
        if schema is not None and schema not in _KNOWN_SCHEMAS:
            return Failure(
                NotFoundError(
                    f"Schema '{schema}' does not exist",
                    entity="schema",
                    key=schema,
                )
            )

        columns = {
            "table_schema": ColumnType.TEXT,
            "table_name": ColumnType.TEXT,
            "table_type": ColumnType.TEXT,
        }
        rows = [row for row in _CATALOG if schema is None or row[0] == schema]
        window = rows[pagination.offset : pagination.offset + pagination.page_size]
        records = tuple(
            Record({"table_schema": s, "table_name": n, "table_type": t})
            for s, n, t in window
        )
        return Success(ResultSet(columns, records))

    async def get_result_set(
        self,
        pagination: Pagination,
        table: str,
        columns: tuple[str, ...],
        schema: str | None = None,
        filters: Filter = Filter(),
    ) -> Result[ResultSet, DomainError]:
        resolved_schema = schema if schema is not None else _DEFAULT_SCHEMA
        entry = _TABLES.get((resolved_schema, table))
        if entry is None:
            return Failure(
                NotFoundError(
                    f"Table '{table}' does not exist", entity="table", key=table
                )
            )

        column_types, rows = entry

        # Projection and filtering both name columns, and filtering on a column
        # that is not projected is legitimate, so both sets are validated.
        requested = [*columns, *(item.column for item in filters.criteria)]
        for name in requested:
            if name not in column_types:
                return Failure(
                    NotFoundError(
                        f"Column '{name}' does not exist in table '{table}'",
                        entity="column",
                        key=name,
                    )
                )

        column_names = tuple(column_types.keys())
        row_mappings = [dict(zip(column_names, values)) for values in rows]

        filtered: list[Mapping[str, Any]] = []
        for row in row_mappings:
            matched = True
            for criterion in filters.criteria:
                try:
                    if not _matches(row, criterion):
                        matched = False
                        break
                except TypeError as error:
                    # An incomparable pair (an integer column against "x") is an
                    # anticipated user error, not a bug: report it as expected
                    # data rather than letting it escape and crash the server.
                    return Failure(
                        ValidationError(
                            f"cannot compare column '{criterion.column}' with "
                            f"the given value: {error}",
                            field=criterion.column,
                        )
                    )
            if matched:
                filtered.append(row)

        # Filtering happens before pagination, so a page is a window over the
        # matched rows and row order is preserved.
        window = filtered[pagination.offset : pagination.offset + pagination.page_size]
        projected_columns = {name: column_types[name] for name in columns}
        records = tuple(
            Record({name: row[name] for name in columns}) for row in window
        )
        return Success(ResultSet(projected_columns, records))

    async def get_record_by(
        self,
        table: str,
        key_column: str,
        key_value: object,
        schema: str | None = None,
    ) -> Result[Record, DomainError]:
        return Failure(
            NotFoundError(
                f"No row in '{table}' with {key_column} = {key_value!r}",
                entity=table,
                key=str(key_value),
            )
        )
