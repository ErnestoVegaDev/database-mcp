# database-mcp

**Give an LLM the ability to explore and query PostgreSQL and MariaDB safely — no typed API in the middle.**

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-2.3.0-1F2937)](https://modelcontextprotocol.io)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.1.4-D71F00?logo=sqlalchemy)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-4169E1?logo=postgresql)](https://www.postgresql.org/)
[![MariaDB](https://img.shields.io/badge/MariaDB-aiomysql-003545?logo=mariadb)](https://mariadb.org/)

## About

Letting a model touch a real database sounds like a one-line integration until you hit the actual problem: a
typed query surface never covers the schema the user has. Every new table, view, or dialect quirk becomes a code
change, and the model is left guessing column names it was never told about. The result is an integration that is
technically safe and practically useless — it can only answer the questions someone predicted in advance.

This server takes the opposite path: **the model writes the SQL, the server only exposes discovery tools and one
read-only execution tool.** There are no DTOs, validators, use cases, or repository abstractions in the query path.
Safety comes from two layers instead of a typed API — a lexical guard that only lets `SELECT` / `SHOW` / `WITH`
through, and a read-only transaction opened on the server side before the statement runs.

The codebase is organized as **vertical slices**: one package per tool under `src/features/`, cross-cutting
concerns under `src/shared/`, and a dependency rule that only allows `features -> shared`. Adding a tool is a new
slice plus one registration line — not a new composition root.

### Key concepts

| Concept | Description |
|---------|-------------|
| **Tool** | An MCP operation the model can call. Five exist: `list_connections`, `get_database_info`, `list_database_objects`, `describe_tables`, `execute_query`. |
| **Engine** | A supported database flavor with its own env var, URL scheme, and SQL dialect. Today: PostgreSQL and MariaDB. |
| **Connection string** | The async SQLAlchemy URL read from an environment variable. Treated as a secret: never logged, never returned by a tool. |
| **Read-only guard** | Lexical classifier that rejects anything that is not a single `SELECT` / `SHOW` / `WITH` statement before it reaches the driver. |
| **Read-only transaction** | The database-side backstop (`SET TRANSACTION READ ONLY` / `START TRANSACTION READ ONLY`) that catches side effects the lexer cannot see. |
| **Vertical slice** | One self-contained feature package under `src/features/`, holding its own MCP tool, payload builder, and per-engine SQL. |

## What you get

This is a headless MCP server, so there is no UI to screenshot — the tool surface *is* the visible product.

| Tool | Input | Returns |
|------|-------|---------|
| `list_connections` | — | Configured engines with their label and env var. Config only: no database round trip, no DSN ever. |
| `get_database_info` | `engine` | Engine label, raw version string, parsed `major`/`minor`/`patch`, capability gates (`procedures`, `cte`, `recursive_cte`, `window_functions`, `json`, `returning`, `upsert`), and installed extensions. |
| `list_database_objects` | `engine`, `kinds?`, `schema?` | `objects` (`kind`, `schema`, `name`) plus counts per kind. `kinds` accepts `table`, `view`, `procedure`, `function`; omitted means all. |
| `describe_tables` | `engine`, `tables`, `schema?` | Columns (type, `nullable`, `default`, `primary_key`) and foreign keys per table, plus a `missing` list for names that do not exist. |
| `execute_query` | `engine`, `sql`, `max_rows?` | Positional `rows` aligned to `columns`, `row_count`, and `truncated`. `max_rows` defaults to 1000, valid range 1–10000. |

Every tool answers with a stable envelope: `{"status": "ok", ...}` on success, or
`{"status": "error", "error": {"type", "message", ...}}` for expected failures. Unexpected driver failures are left
to the MCP boundary and never leak credentials.

## Quick Start

### Prerequisites

- [Python 3.14](https://www.python.org/downloads/) (the virtualenv in this repo was built with 3.14.5)
- An MCP client — [MCP Inspector](https://github.com/modelcontextprotocol/inspector) for a quick check, or any
  client that can spawn a stdio server (Node.js is required only for the Inspector)
- PostgreSQL and/or MariaDB reachable from your machine

### Install

```powershell
git clone https://github.com/ErnestoVegaDev/database-mcp.git
cd database-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
```

`requirements.lock` pins the full dependency set (direct and transitive), so this rebuilds the same environment the
project was verified against. If you prefer the declared view instead of the frozen one, `pyproject.toml` lists the
eight direct dependencies with exact versions.

Optional stacks are declared as extras and are not needed for PostgreSQL or MariaDB:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mssql]"    # pyodbc + aioodbc, for a future SQL Server engine
```

### Verify the environment

```powershell
.\.venv\Scripts\python.exe -c "import mcp, sqlalchemy, asyncpg, aiomysql; print('ok')"
```

### Configure

Each engine is enabled by its own environment variable. Both are optional: an unset variable simply means that
engine is not configured, and the server still boots.

```powershell
# Canonical async schemes
$env:POSTGRES_CONNECTION_STRING = "postgresql+asyncpg://user:password@localhost:5432/mydb"
$env:MARIA_CONNECTION_STRING    = "mysql+aiomysql://user:password@localhost:3306/mydb"
```

Plain schemes copied from a client or a DSN doc are accepted and rewritten to the canonical async scheme:
`postgresql://` and `postgres://` for PostgreSQL, `mysql://` and `mariadb://` for MariaDB. Everything after `://`
is preserved byte-for-byte. A scheme that belongs to a different engine is rejected at startup.

### Run

```powershell
.\.venv\Scripts\python.exe __main__.py
```

The server speaks JSON-RPC over **stdio**, so the client spawns the process — there is no URL to open. To verify it
works without configuring a client:

```powershell
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe __main__.py
```

The Inspector UI opens at <http://localhost:6274> and launches the server for you. Call `list_connections` first: it
tells you which engines the process can actually see.

## Developer Guide

### Project structure

```text
__main__.py                          entry point: puts src/ on sys.path, runs the wrapper on stdio
src/mcp_server_wrapper.py            MCPServerWrapper: SDK server, slice registration, transports, pool disposal
src/shared/                          cross-cutting code, no tool logic
  domain/errors/                     DomainError, NotFoundError, ValidationError(s) + error envelope renderer
  persistence/
    db_context.py                    DbContext: one async engine + session factory
    db_context_options.py            ConnectionOptions + fluent builder, env-var knobs
    supported_engine.py              SupportedEngine catalog: env var, schemes, aliases, label
    connection_registry.py           ConnectionRegistry: env vars -> ConnectionOptions
    db_context_factory.py            DbContextFactory: cached engine -> DbContext dispatch
  sql/read_only.py                   lexical read-only statement guard
src/features/                        vertical slices, one MCP tool per package
  connections/                       list_connections
  database_info/                     get_database_info + capability gates per engine
  database_objects/                  list_database_objects + per-engine catalog queries
  table_schema/                      describe_tables + per-engine structure queries
  query/                             execute_query + JSON-safe row serialization
odd/tasks/                           feature document with decisions, task list, and evidence
```

Dependency direction is one-way: `features -> shared`. A slice never imports another slice; anything two slices need
belongs in `shared/`, and `shared` never imports `features`.

### Architecture

```text
MCP client (stdio JSON-RPC)
        |
        v
MCPServerWrapper ......... composition root: builds the factory, registers 5 slices, disposes pools
        |
        +--> features/* ... tool + payload shape + per-engine static SQL
        |         |
        |         v
        +--> shared/persistence ... ConnectionRegistry -> DbContextFactory -> DbContext (AsyncEngine)
        |         ^
        |         |
        +--> shared/sql/read_only ... guard before the driver (execute_query only)
                  |
                  v
            PostgreSQL / MariaDB
```

Two safety layers stand between model-written SQL and the database: the lexical guard refuses anything that is not a
single `SELECT` / `SHOW` / `WITH` statement (multi-statement payloads included), and the execution session opens a
read-only transaction first. The guard is lexical by design, so the transaction is the semantic backstop for side
effects inside function calls.

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_CONNECTION_STRING` | Async PostgreSQL URL. Canonical `postgresql+asyncpg://…`; accepts `postgresql://` and `postgres://`. | unset (engine not configured) |
| `MARIA_CONNECTION_STRING` | Async MariaDB/MySQL URL. Canonical `mysql+aiomysql://…`; accepts `mysql://` and `mariadb://`. | unset (engine not configured) |
| `MCP_DB_POOL_TIMEOUT_SECONDS` | Seconds to wait for a pooled connection. | `30` |
| `MCP_DB_CONNECT_TIMEOUT_SECONDS` | Driver connect timeout in seconds. | unset (driver default) |
| `MCP_DB_ECHO` | Log emitted SQL to stderr. Accepts `1/true/yes/on` and `0/false/no/off`. | `false` |

### Running and verifying

```powershell
# Run the server (stdio — the client spawns it)
.\.venv\Scripts\python.exe __main__.py
```

There is **no test, lint, format, or typecheck tooling configured** in this repository. Do not assume a runner
exists; if you add one, document the exact command here. For an ad-hoc import check (the `-B` flag avoids writing
`__pycache__`):

```powershell
.\.venv\Scripts\python.exe -B -c @'
import sys
sys.path.insert(0, 'src')
import mcp_server_wrapper
print('import ok')
'@
```

### HTTP transports

`MCPServerWrapper.run_async` accepts `"stdio"`, `"sse"`, and `"streamable-http"`, but `__main__.py` hardcodes
`stdio`. Change the call site to run over HTTP:

- `streamable-http` → `http://127.0.0.1:8000/mcp`
- `sse` → `http://127.0.0.1:8000/sse` (POST messages to `/messages/`)

Host and port come from SDK defaults (`127.0.0.1:8000`). The SDK auto-enables DNS-rebinding protection for
localhost.

### Adding an engine

Adding a member to `SupportedEngine` is two edits **in the catalog** (one enum member, one spec entry). That is not
enough for the tools: each slice owns its dialect-specific statements and feature gates
(`database_info/capabilities.py`, `database_objects/catalog.py`, `table_schema/structure.py`,
`query/execute_query.py`). An engine with no statements for a slice raises `ValueError` rather than borrowing
another dialect's SQL — failing loudly beats returning wrong data.

Adding an engine that is already installed but not wired, such as SQL Server (`pyodbc` / `aioodbc` are present in
`.venv`), also needs an ODBC driver at the OS level, which is an environment decision rather than a code change.

<sub>Built with Python, the MCP Python SDK, SQLAlchemy, and a strong preference for letting the model write its own SQL.</sub>
