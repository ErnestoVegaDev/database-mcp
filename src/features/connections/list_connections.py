"""Slice: list_connections — report the configured database connections.

This tool is the model's entry point: before writing any SQL it needs to know
which engines exist. The answer is deliberately declarative — it reports what
the environment configures — so the tool never opens a connection and never
describes a destination. Probing a live server (type, version, features) is
``get_database_info``'s job.

Privacy rule: a row names the engine and the environment variable that
configures it. The connection string never crosses the wire, not even the
harmless-looking parts of it, because a DSN is a secret by contract.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from shared.persistence import DbContextFactory, SupportedEngine


def _serialize_connection(engine: SupportedEngine) -> dict[str, Any]:
    """Render one configured engine as a JSON-safe row.

    Only the engine's identity and the variable that configures it are exposed.
    The connection string — and every fragment of it — stays server-side.
    """
    return {
        "engine": engine.value,
        "label": engine.label,
        "env_var": engine.env_var,
    }


class ConnectionsTools:
    """MCP tool group for connection discovery.

    The group owns exactly one tool today (``list_connections``); keeping the
    group shape means the composition root registers every slice the same way.
    """

    def __init__(self, factory: DbContextFactory) -> None:
        # The factory is the composition root's single handle on persistence:
        # it already knows which engines the environment configured, so this
        # slice never reads os.environ itself.
        self._factory = factory

    def register(self, mcp: MCPServer) -> None:
        """Register this group's tools on the MCP server."""
        mcp.add_tool(self.list_connections)

    async def list_connections(self) -> dict[str, Any]:
        """List the database connections the environment configures.

        One entry per supported engine whose connection variable is set. An
        environment with nothing configured yields an empty list, which is a
        valid answer rather than an error: the server stays usable and the
        caller can tell it has no engine to query yet.
        """
        return {
            "status": "ok",
            "connections": [
                _serialize_connection(engine)
                for engine in self._factory.configured_engines
            ],
        }
