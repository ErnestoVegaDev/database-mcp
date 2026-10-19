import asyncio
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server_wrapper import MCPServerWrapper


async def main() -> None:
    """Application entry point."""
    server = MCPServerWrapper(name="database-mcp")
    await server.run_async(transport="stdio")


if __name__ == "__main__":
    asyncio.run(main())

#SQL crudo — el SQL lo escribe el modelo
#Superficie tipada
#list_connections - List all database connections
#get_database_info - Get database details (type, version, features)
#list_database_objects - List tables, views, procedures
#describe_tables - Get table structures
#execute_query - Execute read-only SQL (SELECT/SHOW)
#execute_update - Execute write operations (requires confirmation)