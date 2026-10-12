# AGENTS.md

## What this is

Early-stage Python **MCP server** built on the official MCP Python SDK v2.3.0. Despite the
repository name, there is **no database integration yet**: the persistence layer is only a
session factory, the `Repository` port has no implementation, and the single registered data
tool returns mock data.

The code follows a layered `src/` layout (`domain` / `application` / `infrastructure`) with
the MCP edge in `src/infrastructure/mcp_server/`. The entry point is `__main__.py`.

## Behavioral guidelines

Hard rules — apply them on every task, no exceptions.

- **Ask before any file-modifying terminal command.** Never run a command that creates, edits, moves, or deletes files without asking the user for permission first.
- **Ask before querying data outside the repository.** Any command that reads or inspects data outside this repository's path requires explicit permission before it runs.
- **Never modify files outside the repository.** Creating, editing, or deleting anything outside this repository is strictly forbidden under any circumstance — this rule has no exception.

## Layout

```text
__main__.py                          entry point: path bootstrap + run the wrapper (stdio)
src/mcp_server_wrapper.py            MCPServerWrapper: SDK server + component registration + transports
src/domain/                          pure domain; imports nothing outside itself
  enums/                             ColumnType, FilterOperator (StrEnum)
  interfaces/repository.py           Repository (ABC) — read-only port, 3 async methods
  value_objects/                     Filter, FilterCriterion, Pagination, Record, ResultSet
src/application/
  dtos/                              TableCatalogQuery, ListRecordsQuery (frozen dataclasses)
  use_cases/                         empty (no use cases yet)
src/infrastructure/
  persistence/db_context.py          DbContext — async SQLAlchemy engine + async_sessionmaker
  mcp_server/tools/query_tools.py    QueryTools — MCP tool group (get_table_catalog)
  mcp_server/middlewares/            empty
```

Dependency direction is `infrastructure -> application -> domain`, and `domain` depends on
nothing (no SQLAlchemy, no MCP SDK). Keep it that way: the domain must stay framework-free.

## Critical gotchas

- **MCP SDK is `mcp` v2.3.0 and exposes `MCPServer`**: `from mcp.server import MCPServer`.
  The SDK source lives in `.venv/Lib/site-packages/mcp/server/mcpserver/`. There is **no
  `FastMCP`** and **no `mcp.server.fastmcp`** module — most pre-2.x tutorials will fail.
- **The project class is `MCPServerWrapper` — that name only.** `src/mcp_server.py` does not
  exist. There is no `MCPServer` alias (the alias line is commented out at
  `src/mcp_server_wrapper.py:94`) and no `MCPServerBase`. When you see `MCPServer` elsewhere
  (e.g. `query_tools.py`), it is the **SDK** type, not the wrapper.
- **`__main__.py` imports `MCPServerWrapper` and hardcodes `run_async(transport="stdio")`.**
  There is no CLI or environment switch for the transport yet.
- **Two registration styles coexist:** `@self.mcp.tool()` inside
  `MCPServerWrapper._register_tools`, and `mcp.add_tool(self.get_table_catalog)` inside
  `QueryTools.register`. A tool group is unreachable unless `MCPServerWrapper` registers it.
  Currently registered: tools `add` and `get_table_catalog`; resource `greeting://{name}`.
  No prompts (the `_register_prompts` block is commented out).
- **Tool schemas are derived from the method signature** (a Pydantic `arg_model`, one field
  per parameter). A dataclass-typed parameter becomes a **nested object** whose wrapper key
  is **required**: the client must send `{"query": {...}}`, not flattened fields.
- **Return annotations matter:** `-> dict` yields unstructured output (a JSON text block);
  `-> dict[str, Any]` yields structured output.
- **Domain value objects are not JSON-serializable** (frozen dataclasses holding `Mapping` and
  tuples). Map them to plain dicts at the MCP edge; never return a `ResultSet`/`Record`
  straight from a tool.
- **No dependency manifest exists** — no `pyproject.toml`, no `requirements*.txt`, no
  `setup.py`. Dependencies live only in `.venv`. If you introduce a manifest, keep it
  authoritative.
- **`Repository` is an ABC port with no implementation yet.** The adapter that translates it
  into SQL belongs in `infrastructure/persistence`.
- Stale artifact: `src/__pycache__/mcp_server.cpython-314.pyc` is left over from the deleted
  `src/mcp_server.py`; ignore it.

## Environment

- Python 3.14 virtualenv at `.venv` (Windows). Always invoke it explicitly:
  `.\.venv\Scripts\python.exe ...`
- Installed: `mcp` 2.3.0, `mcp-types` 2.3.0, `pydantic` 2.14.0, `SQLAlchemy` 2.1.4,
  `greenlet` 3.5.6, `asyncpg` 0.32.0, `aiosqlite` 0.22.1, `uvicorn` 0.54.0, `starlette` 1.7.0,
  `anyio` 4.15.1, `returns` 0.29.0.
- SQL Server connectivity depends on the OS-level ODBC Driver 17/18 (already installed);
  SQLite async needs `aiosqlite` (present).

## Commands

- Run the server: `.\.venv\Scripts\python.exe __main__.py` (stdio transport).
- **No test, lint, format, or typecheck tooling is configured.** Do not assume a runner
  exists; if you add one, document the exact command here.
- Ad-hoc verification (use `-B` so no `__pycache__` is written):

  ```powershell
  .\.venv\Scripts\python.exe -B -c @'
  import asyncio, sys
  sys.path.insert(0, "src")
  from mcp.server.mcpserver.tools.base import Tool
  from infrastructure.mcp_server.tools import QueryTools

  async def main():
      tool = Tool.from_function(QueryTools().get_table_catalog)
      print(tool.parameters)                                # schema the client receives
      print(await tool.run({"query": {"page": 1}}, None))   # mock response

  asyncio.run(main())
  '@
  ```

## Testing the MCP server

- **stdio (default, no URL).** The server speaks JSON-RPC over stdin/stdout, so the *client*
  spawns the process. With MCP Inspector (requires Node.js):

  ```powershell
  npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe __main__.py
  ```

  The Inspector UI opens at <http://localhost:6274> and launches/connects to the process for
  you, so there is no URL to type.
- **HTTP requires a code change.** `__main__.py` is hardcoded to stdio. Switch the call to
  `run_async(transport="streamable-http")` or `"sse"` and the endpoints are:
  - streamable-http → `http://127.0.0.1:8000/mcp`
  - sse → `http://127.0.0.1:8000/sse` (POST messages to `/messages/`)

  Host/port come from SDK defaults (`127.0.0.1:8000`); the wrapper does not override them.
  The SDK auto-enables DNS-rebinding protection for localhost, allowing `localhost:*` and
  `127.0.0.1:*` hosts and origins.
- **PyCharm** can run and debug the server with a Python Run Configuration (script
  `__main__.py`, interpreter `.venv`). To *consume* the server, use a dedicated MCP client.

> Gotcha: when running inline snippets from PowerShell, use a **single-quoted** here-string
> (`@' ... '@`). A double-quoted one makes PowerShell interpolate `$defs` and other `$` tokens
> and corrupts the payload.

## Project skills

These skills live under `.opencode/skills/` and are exclusive to this repository. Load the
matching one before starting the related task.

- **cicd-basics** — CI/CD fundamentals (GitHub Actions, Docker, blue-green/canary deployments, environment management). Use when setting up pipelines, builds, or deployment workflows.
- **conventional-commits** — Conventional Commits v1.0.0 plus kernel-style commit quality. Use when writing, reviewing, or validating commit messages, choosing a commit type, or generating a CHANGELOG.
- **dotnet-patterns** — Idiomatic C#/.NET patterns, dependency injection, async/await, and maintainability. Use when writing or reviewing C#/.NET code.
- **python-pep8-style** — PEP 8 naming, imports, whitespace, comments/docstrings, and programming recommendations, with the reasoning behind each rule. Use when writing, reviewing, or refactoring Python code, or asking about Python style.
- **readme-writer** — Professional `README.md` structure (title, stack badges, About, concept table, architecture, user vs. developer instructions). Use when creating or rewriting a README.
- **solid** — SOLID principles (SRP/OCP/LSP/ISP/DIP) with warnings against over-application. Use when designing or refactoring object-oriented code.

## Git and repo conventions

- Default branch `main`; remote `origin` → `ErnestoVegaDev/database-mcp`.
- Commit style follows Conventional Commits (e.g. `chore(gitignore): ...`).
- Tracked: `.gitignore`, `AGENTS.md`, `__main__.py`, the `src/**/__init__.py` package files,
  `src/mcp_server_wrapper.py`, and `.opencode/skills/**`.
- `.gitignore` ignores `opencode.json`, `.atl`, `.venv/`, `.idea`, `__pycache__/`, and
  `*.py[cod]`. Note that `.opencode/` is **not** ignored — the skills are versioned on purpose.
- Parts of `src/` may be untracked pending commits; run `git status` before assuming a file
  is under version control.
