import asyncio
import sys
from pathlib import Path

# Running from the repository, src/ holds the top-level packages the slices
# import (features.*, shared.*). Frozen by PyInstaller, --paths src already put
# those packages on sys.path at build time, and __file__ points into the
# extraction directory where src/ does not exist as a directory. Guarding keeps
# the frozen binary from inserting an invalid path it never needed.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server_wrapper import MCPServerWrapper


async def main() -> None:
    """Application entry point."""
    server = MCPServerWrapper(name="database-mcp")
    await server.run_async(transport="stdio")


if __name__ == "__main__":
    asyncio.run(main())