"""Read-only repository port."""

from abc import ABC, abstractmethod

from ..value_objects import Filter, Pagination, Record, ResultSet


class Repository(ABC):
    """Read-only data access contract for the domain.

    Implementations live in the infrastructure layer and translate these
    calls into a concrete database. The domain only ever sees domain types.
    """

    @abstractmethod
    async def get_table_catalog(
        self,
        pagination: Pagination,
        schema: str | None = None,
    ) -> ResultSet:
        """Return one page of the table catalog.

        Result columns: table_schema (TEXT), table_name (TEXT), table_type (TEXT).

        Args:
            pagination: 1-based page window.
            schema: Schema to restrict the catalog to. ``None`` means "no
                schema filter": the adapter resolves it to the dialect's
                effective default (public in Postgres, dbo in SQL Server).
                SQLite has no schemas; its adapter treats ``None`` as its only
                namespace and ignores an explicit value.
        """

    @abstractmethod
    async def get_result_set(
        self,
        pagination: Pagination,
        table: str,
        columns: tuple[str, ...],
        schema: str | None = None,
        filters: Filter = Filter(),
    ) -> ResultSet:
        """Return one page of a table, projected to ``columns``.

        The returned ResultSet declares the ColumnType of every projected
        column, so callers never have to guess types themselves.

        Args:
            pagination: 1-based page window.
            table: Table name to query.
            columns: Columns to reveal, in the requested order.
            schema: Schema that owns the table; ``None`` means the dialect's
                effective default.
            filters: AND-combined predicates. An empty Filter means all rows.
        """

    @abstractmethod
    async def get_record_by(
        self,
        table: str,
        key_column: str,
        key_value: object,
        schema: str | None = None,
    ) -> Record | None:
        """Return the single row whose ``key_column`` equals ``key_value``.

        Returns ``None`` when no row matches.

        Args:
            table: Table name to query.
            key_column: Name of the key column to match on.
            key_value: Value the key column must equal.
            schema: Schema that owns the table; ``None`` means the dialect's
                effective default.
        """
