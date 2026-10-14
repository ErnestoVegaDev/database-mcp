from mcp.server import MCPServer as SDKMCPServer

from infrastructure.mcp_server.tools import QueryTools
from infrastructure.persistence.mock_repository import MockRepository


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
        """Register MCP tools."""
        # Query tools are a separate group; register them on the same server.
        # MockRepository is a temporary stand-in for the SQL adapter; replace
        # it here (composition root) and nothing else in the flow changes.
        QueryTools(MockRepository()).register(self.mcp)

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
