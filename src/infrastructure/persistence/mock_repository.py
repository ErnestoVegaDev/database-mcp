"""Temporary in-memory Repository used until the SQL adapter exists."""

# Absolute imports from src/: infrastructure may depend on application + domain.
from application.interfaces import Repository
from domain.enums import ColumnType
from domain.errors import DomainError, NotFoundError
from domain.value_objects import Filter, Pagination, Record, ResultSet
from returns.result import Failure, Result, Success

# Schemas this stand-in pretends to know; anything else is a NotFoundError.
_KNOWN_SCHEMAS = frozenset({"public", "dbo", "main"})

_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("public", "users", "BASE TABLE"),
    ("public", "orders", "BASE TABLE"),
)


class MockRepository(Repository):
    """Stand-in adapter: canned data behind the real port contract.

    It exercises the full Result flow with no database. Swap it for the SQL
    adapter and neither the use case nor the MCP edge has to change.
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
        return Failure(
            NotFoundError(f"Table '{table}' does not exist", entity="table", key=table)
        )

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
