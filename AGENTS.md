# AGENTS.md

## What this is

Python **MCP server** built on the official MCP Python SDK v2.3.0, following a
**raw-SQL** philosophy: the model writes the SQL, the server only exposes discovery
tools and one read-only execution tool. There is **no typed query surface** — the old
DTOs / validators / use cases / `Repository` port were removed in the raw-SQL rewrite.

Target tool set:

- `list_connections` — list configured database connections
- `get_database_info` — engine type, version, features
- `list_database_objects` — tables, views, procedures
- `describe_tables` — table structures
- `execute_query` — execute read-only SQL (SELECT/SHOW)

The code follows a **vertical slice** layout: one tool (or cohesive tool group) per
package under `src/features/`, with cross-cutting code under `src/shared/`. The entry
point is `__main__.py`.

> **Migration state:** work is tracked in `odd/tasks/raw-sql-mcp.md`. The wrapper
> boots and registers the slices that exist today (`list_connections`); the remaining
> discovery/execution slices (T6-T9) are pending. Registering a new slice is a one-line
> addition in `MCPServerWrapper._register_tools`, so the server grows tool by tool
> without another composition root.

## Behavioral guidelines

Hard rules — apply them on every task, no exceptions.

- **Ask before any file-modifying terminal command.** Never run a command that creates, edits, moves, or deletes files without asking the user for permission first.
- **Ask before querying data outside the repository.** Any command that reads or inspects data outside this repository's path requires explicit permission before it runs.
- **Never modify files outside the repository.** Creating, editing, or deleting anything outside this repository is strictly forbidden under any circumstance — this rule has no exception.

## Layout

```text
__main__.py                          entry point: path bootstrap + run the wrapper (stdio)
src/mcp_server_wrapper.py            MCPServerWrapper: SDK server + component registration + transports
src/shared/                          cross-cutting code, no tool logic
  domain/errors/                     DomainError, NotFoundError, ValidationError(s) — expected failures
  persistence/
    db_context.py                      DbContext — one async engine + async_sessionmaker
    db_context_options.py              ConnectionOptions + fluent builder
    supported_engine.py                SupportedEngine catalog (env var, schemes, label)
    connection_registry.py             ConnectionRegistry — env vars → ConnectionOptions
    db_context_factory.py              DbContextFactory — cached engine → DbContext dispatch
  sql/                                 shared SQL concerns (read_only.py guard, pending T4)
src/features/                        vertical slices — one MCP tool per package
  connections/                         list_connections (T5, registered)
  database_info/                       get_database_info (pending T6)
  database_objects/                    list_database_objects (pending T7)
  table_schema/                        describe_tables (pending T8)
  query/                               execute_query (pending T9)
odd/tasks/raw-sql-mcp.md             feature document: decisions, task list, evidence
```

Dependency direction: `features -> shared`. A slice never imports another slice; if two
slices need the same code, that code belongs in `shared/`. `shared` never imports
`features`.

## Critical gotchas

- **MCP SDK is `mcp` v2.3.0 and exposes `MCPServer`**: `from mcp.server import MCPServer`.
  The SDK source lives in `.venv/Lib/site-packages/mcp/server/mcpserver/`. There is **no
  `FastMCP`** and **no `mcp.server.fastmcp`** module — most pre-2.x tutorials will fail.
- **The project class is `MCPServerWrapper` — that name only.** `src/mcp_server.py` does
  not exist. There is no `MCPServer` alias (the alias line is commented out at the end of
  `src/mcp_server_wrapper.py`) and no `MCPServerBase`. When you see `MCPServer` in code,
  it is the **SDK** type, not the wrapper.
- **`__main__.py` imports `MCPServerWrapper` and hardcodes `run_async(transport="stdio")`.**
  There is no CLI or environment switch for the transport yet.
- **Slices register their tools through `mcp.add_tool(...)` inside a `register(mcp)`
  method**, and `MCPServerWrapper._register_tools` is the composition root that builds the
  factory and calls each slice's `register`. A tool group is unreachable unless the wrapper
  registers it during construction — a slice that is never registered simply does not exist
  for the client. The server exposes **tools only**: there are no MCP resources or prompts,
  so the old `greeting://{name}` resource is gone.
- **No typed surface means no schema layer.** The raw SQL the model sends is validated by
  exactly one thing: the read-only statement guard (`shared/sql/read_only.py`). Never let
  `execute_query` reach the driver without that guard passing, and never reintroduce
  DTOs/validators/use cases "for safety" — the guard is the safety boundary.
- **Connections come from environment variables, one per supported engine:**
  `POSTGRES_CONNECTION_STRING` (async Postgres, canonical `postgresql+asyncpg`) and
  `MARIA_CONNECTION_STRING` (async MySQL/MariaDB, canonical `mysql+aiomysql`). The plain
  schemes users copy from a client or a DSN doc are accepted as **aliases** —
  `postgresql://` and `postgres://` for Postgres, `mysql://` and `mariadb://` for MariaDB —
  and are rewritten at the string level to the engine's single canonical async scheme.
  Each engine has exactly one driver, so an alias is a spelling fix, not a driver choice;
  everything after `://` (credentials, encoding, query params) is preserved byte-for-byte.
  An unset variable means "engine not configured" — the server must stay bootable and
  report the engine as absent, not crash. `shared/persistence/connection_registry.py` reads
  them into a `ConnectionRegistry` (validating each set URL's scheme against its engine's
  canonical and alias schemes) and warns about unknown `*_CONNECTION_STRING` variables.
  `DbContextFactory.get(engine)` returns the cached `DbContext`, or a `Failure(NotFoundError)`
  for an unconfigured engine; a creation failure is sanitized to the exception class name.
- **A connection string is a secret.** `ConnectionOptions.connection_string` is declared
  `repr=False` on purpose; never log a DSN, never interpolate it into a message, and never
  return it from a tool. Error messages carry the exception **class name** only; the full
  exception goes to `logging.getLogger(__name__)` (stderr).
- **Expected failures are values, not exceptions.** Shared domain errors
  (`shared/domain/errors`) describe anticipated failures and are rendered by the MCP edge
  as `{"status": "ok", ...}` / `{"status": "error", "error": {...}}`. Unexpected exceptions
  (bugs, driver failures) are deliberately left uncaught at the edge: the SDK tool boundary
  reports them as `is_error=True` without leaking internals.
- **stdout is the JSON-RPC stream.** Diagnostics go to `logging` (stderr), never `print()` —
  a stray `print` on the stdio transport corrupts the protocol.
- **Imports are absolute from `src/`.** `__main__.py` puts `src/` on `sys.path`, so slices
  import as `from shared.persistence import DbContext` and the wrapper as
  `from features.connections import ...`. Imports inside a single package stay relative
  (`from .errors import DomainError`). Cross-slice relative imports (`from ..shared...`)
  are a trap: they silently change meaning when a module moves.
- **Row values must be mapped to JSON-safe types at the slice edge.** Raw results carry
  `Decimal`, `datetime`, `UUID`, and `bytes`, which the MCP layer cannot serialize; widen
  them to plain Python/JSON types in the slice that returns them, never deep inside
  `shared`.
- **No dependency manifest exists** — no `pyproject.toml`, no `requirements*.txt`, no
  `setup.py`. Dependencies live only in `.venv`. If you introduce a manifest, keep it
  authoritative.
- **`ORDER BY`, or pagination lies.** The server no longer paginates for the caller (raw
  SQL owns LIMIT/OFFSET), but when a slice pages internally it must impose a stable order
  or the same row can appear on two pages.

## Environment

- Python 3.14 virtualenv at `.venv` (Windows). Always invoke it explicitly:
  `.\.venv\Scripts\python.exe ...`
- Installed: `mcp` 2.3.0, `mcp-types` 2.3.0, `pydantic` 2.14.0, `SQLAlchemy` 2.1.4,
  `greenlet` 3.5.6, `asyncpg` 0.32.0 (PostgreSQL), `aiomysql` (MariaDB), `aiosqlite` 0.22.1,
  `uvicorn` 0.54.0, `starlette` 1.7.0, `anyio` 4.15.1, `returns` 0.29.0.
- **Both async drivers are installed** (`asyncpg` for PostgreSQL, `aiomysql` for MariaDB),
  so both engines are usable end to end.
- **Configuration environment variables:**
  - `POSTGRES_CONNECTION_STRING` — async PostgreSQL URL. Canonical scheme
    `postgresql+asyncpg://...`; the plain `postgresql://` / `postgres://` are accepted
    aliases rewritten to it.
  - `MARIA_CONNECTION_STRING` — async MariaDB URL. Canonical scheme
    `mysql+aiomysql://...`; the plain `mysql://` / `mariadb://` are accepted aliases
    rewritten to it.
  - `MCP_DB_POOL_TIMEOUT_SECONDS`, `MCP_DB_CONNECT_TIMEOUT_SECONDS`, `MCP_DB_ECHO` —
    shared engine knobs (see `db_context_options.py`).

## Commands

- Run the server: `.\.venv\Scripts\python.exe __main__.py` (stdio transport). The wrapper
  boots and registers the slices written so far (see Migration state above).
- **No test, lint, format, or typecheck tooling is configured.** Do not assume a runner
  exists; if you add one, document the exact command here.
- Ad-hoc verification (use `-B` so no `__pycache__` is written):

  ```powershell
  .\.venv\Scripts\python.exe -B -c @'
  import sys
  sys.path.insert(0, 'src')
  import mcp_server_wrapper
  print('import ok')
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
- **HTTP needs a different call site.** `MCPServerWrapper.run_async` already accepts a transport
  (`"stdio"`, `"sse"`, `"streamable-http"`), but `__main__.py` invokes it with the default
  `stdio`. Pass `transport="streamable-http"` (or `"sse"`) there and the endpoints are:
  - streamable-http → `http://127.0.0.1:8000/mcp`
  - sse → `http://127.0.0.1:8000/sse` (POST messages to `/messages/`)

  Host/port come from SDK defaults (`127.0.0.1:8000`); the wrapper does not override them.
  The SDK auto-enables DNS-rebinding protection for localhost, allowing `localhost:*` and
  `127.0.0.1:*` hosts and origins.
- **PyCharm** can run and debug the server with a Python Run Configuration (script
  `__main__.py`, interpreter `.venv`). To *consume* the server, use a dedicated MCP client.

> Gotcha: when running inline snippets from PowerShell, use a **single-quoted** here-string
> (`@' ... '@`) and **single quotes inside the Python code**. A double-quoted here-string makes
> PowerShell interpolate `$defs` and other `$` tokens, and PowerShell 5.1 mangles the double
> quotes it forwards to a native executable — either way the payload arrives corrupted.
> Separate commands with `;`, not `&&`: this shell is Windows PowerShell 5.1, where `&&` is a
> parse error.

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
- Tracked: all of `src/`, plus `.gitignore`, `AGENTS.md`, `__main__.py`, and
  `.opencode/skills/**`.
- `.gitignore` ignores `opencode.json`, `.atl`, `.venv/`, `.idea`, `__pycache__/`, and
  `*.py[cod]`. Note that `.opencode/` is **not** ignored — the skills are versioned on purpose.
- Task tracking lives in `odd/tasks/<feature-name>.md`; run `git status` before assuming a
  file is under version control (new slice packages start untracked).
