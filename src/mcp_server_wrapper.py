import logging

from mcp.server import MCPServer as SDKMCPServer

from features.connections import ConnectionsTools
from features.database_objects import DatabaseObjectsTools
from shared.persistence import ConnectionRegistry, DbContextFactory

# Diagnostics go to logging (stderr), never to print(). On the stdio transport
# stdout carries the JSON-RPC stream, so a stray print() corrupts the protocol
# and the client sees a parse error instead of a warning.
logger = logging.getLogger(__name__)


class MCPServerWrapper:
    """Wrapper class for the Database MCP server.

    Provides a clean, application-specific abstraction around the MCP Python SDK's
    MCPServer. It encapsulates initialization, component registration (tools),
    and both synchronous and asynchronous startup logic.
    """

    def __init__(self, name: str = "database-mcp") -> None:
        # Create the base MCP server instance (MCP Python SDK v2.3.0)
        self.mcp = SDKMCPServer(name)

        # Register server components. The composition root builds the
        # persistence pipeline here and hands each slice what it needs.
        self._register_tools()
        # self._register_prompts()  # Uncomment when prompts are added

    def _register_tools(self) -> None:
        """Register the MCP tool groups against the shared persistence factory.

        Every slice receives the same ``DbContextFactory`` and registers its
        tools on the one server. A slice that is never registered here simply
        does not exist for the client, so this method is the single place that
        decides which tools the server exposes.
        """
        factory = self._build_factory()
        ConnectionsTools(factory).register(self.mcp)
        DatabaseObjectsTools(factory).register(self.mcp)

        # T6-T9 register the remaining groups the exact same way: import the
        # slice and call ``<Group>(factory).register(self.mcp)`` here. Adding a
        # tool is a one-line change in this method, never a new composition root.

    def _build_factory(self) -> DbContextFactory:
        """Build the persistence pipeline from the environment.

        An empty environment is a valid state: with no engine configured the
        factory still answers every call, returning "not configured" for the
        tools that need a specific engine. That is why there is no stand-in
        repository any more — "no database" is a first-class answer, not a
        reason to refuse to boot.

        Returns:
            The factory that dispatches engines to their cached contexts. It is
            also stored on ``self`` because the shutdown path disposes it.
        """
        registry = ConnectionRegistry.from_env()
        factory = DbContextFactory(registry)
        self._factory = factory

        engines = factory.configured_engines
        if engines:
            # Names only: a label can never be, or contain, a DSN.
            logger.info(
                "Configured engines: %s.",
                ", ".join(engine.label for engine in engines),
            )
        else:
            logger.info(
                "No database engine configured; discovery tools will report "
                "an empty connection list."
            )
        return factory

    # def _register_prompts(self) -> None:
    #     """Register MCP prompts."""
    #     pass

    def run(self, transport: str = "stdio") -> None:
        """Start the MCP server using a synchronous transport.

        This path cannot await the asynchronous pool shutdown, so cached
        database contexts are not disposed here. Use :meth:`run_async` (the
        application entry point) when closing pooled connections matters.

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

        Whatever the outcome of the transport — a clean return, an unsupported
        name, or a mid-serve exception — the cached database pools are disposed
        exactly once on the way out. A ``finally`` around the whole dispatch
        guarantees the cleanup runs even when the transport raises, and the
        original exception still propagates.

        Args:
            transport: Transport to use ('stdio', 'sse', 'streamable-http').
        """
        transport = transport.lower().strip()

        try:
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
        finally:
            await self._factory.dispose_all()


# Alias to maintain the requested naming convention
# MCPServer = MCPServerWrapper
