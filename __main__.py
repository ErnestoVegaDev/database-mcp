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
