"""MCP tools that expose read-only query capabilities."""

from mcp.server import MCPServer

from application.dtos import TableCatalogQuery


class QueryTools:
    """Controller-like grouping of query tools.

    Every public method here is a candidate MCP tool. The SDK validates the
    received arguments against the method signature before the body runs, so
    a DTO parameter arrives as a real, validated instance of that DTO.
    """

    def __init__(self) -> None:
        # The repository port is injected here once the persistence adapter
        # exists; the current implementations return mock data.
        pass

    def register(self, mcp: MCPServer) -> None:
        """Register this group's tools on the MCP server.

        Only get_table_catalog is wired for now; the other methods stay
        unregistered until their DTOs are designed.
        """
        mcp.add_tool(self.get_table_catalog)

    async def get_table_catalog(self, query: TableCatalogQuery) -> dict:
        """Return one page of the table catalog.

        MOCK: there is no database yet. The response echoes the received DTO
        so the input flow can be verified end to end, and returns a fixed
        page shaped like the future ResultSet.
        """
        return {
            "received_query": {
                "schema": query.schema,
                "page": query.page,
                "page_size": query.page_size,
            },
            "columns": {
                "table_schema": "text",
                "table_name": "text",
                "table_type": "text",
            },
            "records": [
                {
                    "table_schema": query.schema or "public",
                    "table_name": "users",
                    "table_type": "BASE TABLE",
                },
                {
                    "table_schema": query.schema or "public",
                    "table_name": "orders",
                    "table_type": "BASE TABLE",
                },
            ],
        }

    async def get_list_records(self, table: str, limit: int = 20) -> list[dict]:
        """List records from a table (not registered yet)."""
        ...

    async def get_record(self, table: str, limit: int = 20) -> dict:
        """Return one record from a table (not registered yet)."""
        ...
