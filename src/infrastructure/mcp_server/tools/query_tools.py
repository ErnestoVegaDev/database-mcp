"""MCP tools that expose read-only query capabilities."""

from mcp.server import MCPServer
from returns.result import Failure

from application.dtos import ListRecordsQuery, TableCatalogQuery
from application.interfaces import Repository
from application.use_cases import GetListRecords, GetTableCatalog
from domain.errors import DomainError, NotFoundError, ValidationError, ValidationErrors
from domain.value_objects import ResultSet


def _serialize_result_set(result_set: ResultSet) -> dict:
    """Flatten a ResultSet into JSON-safe primitives for the wire.

    Domain value objects (Mapping-based, non-serializable) never cross the
    MCP boundary themselves; they become plain dicts here.
    """
    return {
        "columns": {
            name: column_type.value for name, column_type in result_set.columns.items()
        },
        "records": [dict(record.values) for record in result_set.records],
    }


def _describe_error(error: DomainError) -> dict:
    """Render a DomainError as a discriminated, JSON-safe payload."""
    payload: dict = {"type": type(error).__name__, "message": str(error)}

    if isinstance(error, ValidationErrors):
        payload["errors"] = [
            {"field": item.field, "message": item.message} for item in error.errors
        ]
    elif isinstance(error, ValidationError):
        payload["field"] = error.field

    if isinstance(error, NotFoundError):
        payload["entity"] = error.entity
        payload["key"] = error.key

    return payload


class QueryTools:
    """Controller-like grouping of query tools.

    Every public method here is a candidate MCP tool. The SDK validates the
    received arguments against the method signature before the body runs, so
    a DTO parameter arrives as a real, validated instance of that DTO.

    The boundary job is narrow: call the use case and translate its Result
    into a JSON-serializable payload. The tool never builds domain objects or
    inspects the database directly.

    Error contract:
        - Expected failures are values, not exceptions. The use case returns
          ``Failure(DomainError)`` and the tool renders it as a structured
          payload the caller can act on.
        - Unexpected exceptions (bugs, driver failures) are deliberately NOT
          caught here. The SDK's tool boundary owns them: it logs the traceback
          server-side, keeps the internal message away from the client, and
          returns ``is_error=True``. Adding a local try/except would duplicate
          that boundary and misreport a crash as a normal, ``is_error=False``
          result.
        - Anticipatable technical failures (e.g. the database being down) are
          mapped to a ``DomainError`` inside the persistence adapter, turning
          them into expected failures instead of crashes.
    """

    def __init__(self, repository: Repository) -> None:
        # One injected port feeds both use cases: the tools differ in the DTO
        # and the use case they call, not in where their data comes from.
        self._get_table_catalog = GetTableCatalog(repository)
        self._get_list_records = GetListRecords(repository)

    def register(self, mcp: MCPServer) -> None:
        """Register this group's tools on the MCP server.

        get_table_catalog and get_list_records are wired; get_record stays
        unregistered until its DTO is designed.
        """
        mcp.add_tool(self.get_table_catalog)
        mcp.add_tool(self.get_list_records)

    async def get_table_catalog(self, query: TableCatalogQuery) -> dict:
        """Return one page of the table catalog.

        Success carries the requested page; an expected failure (invalid
        input, unknown schema) comes back as a structured error payload
        instead of an exception.
        """
        result = await self._get_table_catalog.execute(query)
        if isinstance(result, Failure):
            return {"status": "error", "error": _describe_error(result.failure())}
        return {"status": "ok", **_serialize_result_set(result.unwrap())}

    async def get_list_records(self, query: ListRecordsQuery) -> dict:
        """Return one page of a filtered, projected table.

        Success carries the requested page; an expected failure (invalid input,
        unknown table or column) comes back as a structured error payload
        instead of an exception.
        """
        result = await self._get_list_records.execute(query)
        if isinstance(result, Failure):
            return {"status": "error", "error": _describe_error(result.failure())}
        return {"status": "ok", **_serialize_result_set(result.unwrap())}

    async def get_record(self, table: str, limit: int = 20) -> dict:
        """Return one record from a table (not registered yet)."""
        ...
