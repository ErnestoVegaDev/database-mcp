import logging

from mcp.server import MCPServer as SDKMCPServer

from application.interfaces import Repository
from infrastructure.mcp_server.tools import QueryTools
from infrastructure.persistence.db_context import DbContext
from infrastructure.persistence.db_context_options import (
    ENV_CONNECTION_STRING,
    DbContextOptions,
)
from infrastructure.persistence.mock_repository import MockRepository
from infrastructure.persistence.sqlalchemy_repository import SqlAlchemyRepository

# Diagnostics go to logging (stderr), never to print(). On the stdio transport
# stdout carries the JSON-RPC stream, so a stray print() corrupts the protocol
# and the client sees a parse error instead of a warning.
logger = logging.getLogger(__name__)


class MCPServerWrapper:
    """Wrapper class for the Database MCP server.

    Provides a clean, application-specific abstraction around the MCP Python SDK's
    MCPServer. It encapsulates initialization, component registration (tools,
    resources, and prompts), and both synchronous and asynchronous startup logic.
    """

    def __init__(self, name: str = "database-mcp") -> None:
        # Create the base MCP server instance (MCP Python SDK v2.3.0)
        self.mcp = SDKMCPServer(name)

        # Register server components
        self._register_tools()
        self._register_resources()
        # self._register_prompts()  # Uncomment when prompts are added

    def _register_tools(self) -> None:
        """Register MCP tools against the repository the configuration selects."""
        # Query tools are a separate group; register them on the same server.
        # The composition root is the ONLY place that chooses a concrete
        # adapter: QueryTools receives the port, so swapping the implementation
        # here changes nothing in the use cases or the MCP edge.
        self._repository = self._build_repository()
        QueryTools(self._repository).register(self.mcp)

    def _build_repository(self) -> Repository:
        """Select the SQL adapter when a database is configured, else the stand-in.

        The "is a database configured?" question is answered by the options
        class, not by reading the environment here, so the env-var contract
        stays in one module (D8).
        """
        options = DbContextOptions.from_env_or_none()
        if options is None:
            # No database configured: keep the server runnable by serving the
            # in-memory fixture, but make the fallback visible instead of
            # silently pretending the fixture is real data.
            logger.warning(
                "No database configured (%s is unset); serving fixture data "
                "from MockRepository. Set %s to use a real database.",
                ENV_CONNECTION_STRING,
                ENV_CONNECTION_STRING,
            )
            return MockRepository()

        # A configured database selects the real adapter. Building the
        # DbContext is lazy: it creates the engine/pool but does not connect
        # until the first query, so an unreachable database surfaces per request
        # as a sanitized failure rather than at startup.
        self._db_context = DbContext(options)
        logger.info("Database configured; using SqlAlchemyRepository.")
        return SqlAlchemyRepository(self._db_context)

    def _register_resources(self) -> None:
        """Register MCP resources."""

        @self.mcp.resource("greeting://{name}")
        def greeting(name: str) -> str:
            """Greet someone by name."""
            return f"Hello, {name}!"

    # def _register_prompts(self) -> None:
    #     """Register MCP prompts."""
    #     pass

    def run(self, transport: str = "stdio") -> None:
        """Start the MCP server using a synchronous transport.

        Args:
            transport: Transport to use ('stdio', 'sse', 'streamable-http').
        """
        transport = transport.lower().strip()

        if transport == "stdio":
            self.mcp.run(transport="stdio")
            return

        if transport == "sse":
            self.mcp.run(transport="sse")
            return

        if transport == "streamable-http":
            self.mcp.run(transport="streamable-http")
            return

        raise ValueError(f"Unsupported transport: {transport}")

    async def run_async(self, transport: str = "stdio") -> None:
        """Start the MCP server using an asynchronous transport.

        Preferred for I/O-bound workloads (e.g., database access, network calls).

        Args:
            transport: Transport to use ('stdio', 'sse', 'streamable-http').
        """
        transport = transport.lower().strip()

        if transport == "stdio":
            await self.mcp.run_stdio_async()
            return

        if transport == "sse":
            await self.mcp.run_sse_async()
            return

        if transport == "streamable-http":
            await self.mcp.run_streamable_http_async()
            return

        raise ValueError(f"Unsupported transport: {transport}")


# Alias to maintain the requested naming convention
# MCPServer = MCPServerWrapper
