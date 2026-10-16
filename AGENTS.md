# AGENTS.md

## What this is

Early-stage Python **MCP server** built on the official MCP Python SDK v2.3.0. The persistence
layer is a SQLAlchemy `DbContext` plus a read-only SQL adapter (`SqlAlchemyRepository`); when no
database is configured the composition root falls back to the in-memory `MockRepository` stand-in.
The registered tools serve data through application use cases, so neither implementation is known
above the `Repository` port.

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
  errors/                            DomainError, NotFoundError, ValidationError(s) — expected failures
  value_objects/                     Filter, FilterCriterion, Pagination, Record, ResultSet
src/application/
  dtos/                              TableCatalogQuery, ListRecordsQuery, FilterCriterionQuery (pydantic dataclasses)
  interfaces/repository.py           Repository (ABC) — read-only port, 3 async methods returning Result
  use_cases/get_table_catalog.py     GetTableCatalog — validate, paginate, ask the port for a page
  use_cases/get_list_records.py      GetListRecords — validate, translate filters, ask the port for a page
  validators/                        TableCatalogQueryValidator, ListRecordsQueryValidator — input rules checked before the domain
src/infrastructure/
  persistence/db_context.py             DbContext — async SQLAlchemy engine + async_sessionmaker
  persistence/db_context_options.py     DbContextOptions + fluent builder (MCP_DB_* env vars, from_env_or_none seam)
  persistence/mock_repository.py        MockRepository — in-memory stand-in that implements the port and the filter operators
  persistence/column_type_mapping.py    SQLAlchemy type -> ColumnType (ordered isinstance probes)
  persistence/sqlalchemy_repository.py  SqlAlchemyRepository — read-only Core adapter behind the port
  mcp_server/tools/query_tools.py    QueryTools — MCP tool group (get_table_catalog, get_list_records)
  mcp_server/middlewares/            empty
```

Dependency direction is `infrastructure -> application -> domain`, and `domain` depends on
nothing (no SQLAlchemy, no MCP SDK). Keep it that way: the domain must stay framework-free. The
`Repository` port lives in `application/interfaces` because it describes how the application
reaches persistence, so the domain layer holds only pure domain types.

## Critical gotchas

- **MCP SDK is `mcp` v2.3.0 and exposes `MCPServer`**: `from mcp.server import MCPServer`.
  The SDK source lives in `.venv/Lib/site-packages/mcp/server/mcpserver/`. There is **no
  `FastMCP`** and **no `mcp.server.fastmcp`** module — most pre-2.x tutorials will fail.
- **The project class is `MCPServerWrapper` — that name only.** `src/mcp_server.py` does not
  exist. There is no `MCPServer` alias (the alias line is commented out at the end of
  `src/mcp_server_wrapper.py`) and no `MCPServerBase`. When you see `MCPServer` elsewhere
  (e.g. `query_tools.py`), it is the **SDK** type, not the wrapper.
- **`__main__.py` imports `MCPServerWrapper` and hardcodes `run_async(transport="stdio")`.**
  There is no CLI or environment switch for the transport yet.
- **Two registration styles coexist:** `MCPServerWrapper` registers its own components with
  decorators (`@self.mcp.resource("greeting://{name}")`), while a tool group registers itself
  through `mcp.add_tool(self.get_table_catalog)` inside `QueryTools.register`. A tool group is
  unreachable unless `MCPServerWrapper` registers it during construction. Currently registered:
  tools `get_table_catalog` and `get_list_records`; resource `greeting://{name}`. No prompts (the
  `_register_prompts` block is commented out).
- **Tool schemas are derived from the method signature** (a Pydantic `arg_model`, one field
  per parameter). A dataclass-typed parameter becomes a **nested object** whose wrapper key
  is **required**: the client must send `{"query": {...}}`, not flattened fields.
- **Boundary DTOs are strict pydantic dataclasses:**
  `pydantic.dataclasses.dataclass(frozen=True, slots=True, config=ConfigDict(extra="forbid"))`.
  `extra="forbid"` is not cosmetic — pydantic silently DROPS an unknown key by default, so a
  mistyped filter key would return **unfiltered** rows with no error at all. With it the SDK
  rejects extras as a `ToolError` naming the path (`query.filters.0.bogus`). Two consequences:
  `FilterCriterionQuery.value` is typed `Any` on purpose (`Any` is not coerced, so `5`, `"5"` and
  `true` stay distinct comparisons), and the per-operator value rules live in the **validator**, not
  in the schema, because only the validator can answer with a structured `{"status": "error"}`.
  A filter is AND-combined: `filters` is a flat list, and an empty list means every row matches.
- **Return annotations matter:** `-> dict` yields unstructured output (a JSON text block);
  `-> dict[str, Any]` yields structured output.
- **Domain value objects are not JSON-serializable** (frozen dataclasses holding `Mapping` and
  tuples). Map them to plain dicts at the MCP edge; never return a `ResultSet`/`Record`
  straight from a tool. `QueryTools._serialize_result_set` is the only place that flattening
  happens today.
- **Expected failures are values, not exceptions.** The port and the use case return
  `Result[..., DomainError]` from the `returns` library; the MCP edge unwraps it into
  `{"status": "ok", ...}` or `{"status": "error", "error": {...}}`. So: never raise for a missing
  row, an unknown schema, or a rejected request — return `Failure`, and never wrap a tool body in
  `try/except` to catch domain failures. Unexpected exceptions (bugs, driver failures) are
  deliberately left uncaught at the edge: the SDK tool boundary already reports them as
  `is_error=True` without leaking internals, and a local catch would reclassify a crash as a
  normal result.
- **Imports are absolute from `src/`.** Modules in `src/application` and `src/infrastructure`
  import across packages in absolute form (`from domain.errors import DomainError`), because the
  entry point puts `src/` on `sys.path`; imports inside a single package stay relative
  (`from .errors import DomainError`). Cross-layer relative imports are a trap: `from ..value_objects`
  silently changes meaning when the module moves, which is exactly why
  `application/interfaces/repository.py` imports the domain absolutely.
- **No dependency manifest exists** — no `pyproject.toml`, no `requirements*.txt`, no
  `setup.py`. Dependencies live only in `.venv`. If you introduce a manifest, keep it
  authoritative.
- **`Repository` is an ABC port with two implementations: `MockRepository`** (in-memory, canned
  rows, no database) **and `SqlAlchemyRepository`** (read-only, real database, built on SQLAlchemy
  Core + reflection). Both sit in `infrastructure/persistence`; the port is chosen in exactly one
  place, `MCPServerWrapper._build_repository`, because `QueryTools` receives the port by constructor
  injection.
- **The mock filters with SQL semantics — that behavior is the contract the SQL adapter must
  match.** A comparison against a stored `NULL` excludes the row (three-valued logic) instead of
  raising, which is why `ne` and `not_in` never match `NULL` rows even though Python's `!=` and
  `not in` would. `like` is case-sensitive (Postgres-flavored): `%` is any run of characters, `_`
  is exactly one character, everything else is literal. A comparison between incompatible types
  (an integer column against `"x"`) is an anticipated caller mistake, so it is mapped to a
  `ValidationError` rather than escaping as a `TypeError`.
- **Persistence is selectable — `SqlAlchemyRepository` or `MockRepository`.** The composition root
  (`MCPServerWrapper._build_repository`) asks `DbContextOptions.from_env_or_none()`: a non-blank
  `MCP_DB_CONNECTION_STRING` selects the SQL adapter, otherwise it logs a **warning on stderr**
  through `logging.getLogger(__name__)` and serves the in-memory stand-in. The env knowledge lives
  in the options class, not in the wrapper, and the warning is never a `print`: on the stdio
  transport stdout carries the JSON-RPC stream, so a `print` there corrupts the protocol.
- **The adapter keeps every DB call inside `session.run_sync`.** `AsyncSession.run_sync` hands the
  callback the SYNC `Session` (not a `Connection`), so `sqlalchemy_repository` borrows the
  connection with `sync_session.connection()` and drives `sqlalchemy.inspect`, reflection
  (`Table(name, MetaData(), schema=..., autoload_with=conn)`) and Core `select(...)` through it.
  Never touch the async connection outside `run_sync`. Reflection quotes identifiers and parameter
  binding carries values, so no identifier or value is ever interpolated into a SQL string.
- **Adapter error mapping: expected failures are values, driver failures are sanitized.** For
  **expected** cases return `Failure(NotFoundError(...))`: missing table (`entity="table"`),
  missing schema (`entity="schema"`), missing column (`entity="column"`), missing row
  (`entity="row"`). Catch only SQLAlchemy's hierarchy — `NoSuchTableError` subclasses
  `InvalidRequestError` → `SQLAlchemyError`, so its handler must come **first** when both are
  caught. Any other `SQLAlchemyError` becomes `Failure(DomainError)` with a **sanitized** message:
  only the exception CLASS name, never the connection string, URL, credentials or raw driver text,
  because the MCP edge renders it to the caller. The full exception is logged at error level to
  `logging.getLogger(__name__)` (stderr) so operators keep the detail. A bare `except` is banned:
  it would reclassify a bug as a normal result.
- **`ORDER BY`, or pagination lies.** `LIMIT`/`OFFSET` without a stable order can return the same
  row on two pages. `get_table_catalog` orders by `(table_schema, table_name)`; `get_result_set`
  orders by the reflected primary key, and when the table has **none** it imposes no order, so page
  stability is then the caller's risk (a keyless table has no stable identity). The mock preserves
  insertion order instead — the same while rows are stable, but never a promise.
- **Schema resolution (D3).** `schema=None` means "no schema filter" and resolves to
  `Inspector.default_schema_name` (`public` / `dbo`); the catalog reports it as `table_schema`. On
  **SQLite** (no schemas) an explicit schema is **ignored** and the catalog reports the namespace
  label `"main"`. On a dialect that has schemas, an explicit value absent from
  `Inspector.get_schema_names()` is `Failure(NotFoundError(entity="schema"))`.
- **`Decimal` is widened to `float` at the adapter boundary.** A numeric column is declared
  `ColumnType.FLOAT` (the domain enum has no decimal member), so the declared type must be true of
  the delivered value; `_normalize_value` converts `Decimal`→`float` and nothing else. The
  precision tradeoff is real and documented in the helper, not hidden.
- **`LIKE` case sensitivity belongs to the dialect, not the mock.** The mock is Postgres-flavored
  (case-sensitive on ASCII); SQLite's `LIKE` is case-insensitive, so the same pattern can match
  more rows there. The adapter does exactly what `.like(pattern)` does on the configured dialect.
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
- **Configure the database with `MCP_DB_CONNECTION_STRING`** (an async SQLAlchemy URL:
  `sqlite+aiosqlite:///...`, `postgresql+asyncpg://...`, `mssql+aioodbc://...`). Set it to select
  `SqlAlchemyRepository`; leave it unset and the server serves `MockRepository` with a stderr
  warning. `MCP_DB_POOL_TIMEOUT_SECONDS`, `MCP_DB_CONNECT_TIMEOUT_SECONDS` and `MCP_DB_ECHO` tune
  the pool. The "is a database configured?" decision is `DbContextOptions.from_env_or_none()`.

## Commands

- Run the server: `.\.venv\Scripts\python.exe __main__.py` (stdio transport).
- **No test, lint, format, or typecheck tooling is configured.** Do not assume a runner
  exists; if you add one, document the exact command here.
- Ad-hoc verification (use `-B` so no `__pycache__` is written):

  ```powershell
  .\.venv\Scripts\python.exe -B -c @'
  import asyncio, sys
  sys.path.insert(0, 'src')
  from mcp.server.mcpserver.tools.base import Tool
  from infrastructure.mcp_server.tools import QueryTools
  from infrastructure.persistence.mock_repository import MockRepository

  async def main():
      tool = Tool.from_function(QueryTools(MockRepository()).get_table_catalog)
      print(tool.parameters)                               # schema the client receives
      print(await tool.run({'query': {'page': 1}}, None))  # {'status': 'ok', ...}
      print(await tool.run({'query': {'page': 0}}, None))  # {'status': 'error', ...}

  asyncio.run(main())
  '@
  ```
- Ad-hoc verification of the filter flow (same here-string rules apply):

  ```powershell
  .\.venv\Scripts\python.exe -B -c @'
  import asyncio, sys
  sys.path.insert(0, 'src')
  from mcp.server.mcpserver.tools.base import Tool
  from infrastructure.mcp_server.tools import QueryTools
  from infrastructure.persistence.mock_repository import MockRepository

  async def main():
      tool = Tool.from_function(QueryTools(MockRepository()).get_list_records)
      query = {'table': 'users', 'columns': ['id', 'name'],
               'filters': [{'column': 'age', 'operator': 'gt', 'value': 40}]}
      print(await tool.run({'query': query}, None))   # {'status': 'ok', 'records': [...]}

      missing = dict(query, filters=[{'column': 'age', 'operator': 'gt'}])
      print(await tool.run({'query': missing}, None)) # {'status': 'error', ...} -> validator

      try:
          await tool.run({'query': dict(query, limit=5)}, None)
      except Exception as error:
          print(type(error).__name__, 'limit is gone; use page_size')  # ToolError -> schema

  asyncio.run(main())
  '@
  ```

  That snippet shows the three channels in one place: a successful page, a business rejection
  rendered as `{"status": "error"}`, and a shape error raised by the SDK as `ToolError`.
- Ad-hoc verification against the SQL adapter. This builds the context directly
  (`DbContextOptions(connection_string=...)`); in the running server the same switch is driven by
  `MCP_DB_CONNECTION_STRING`. **Executed**, with the observed output below the snippet:

  ```powershell
  .\.venv\Scripts\python.exe -B -c @'
  import asyncio, sys
  sys.path.insert(0, 'src')
  from sqlalchemy import MetaData, Table, Column, Integer, String
  from mcp.server.mcpserver.tools.base import Tool
  from infrastructure.persistence.db_context import DbContext
  from infrastructure.persistence.db_context_options import DbContextOptions
  from infrastructure.persistence.sqlalchemy_repository import SqlAlchemyRepository
  from infrastructure.mcp_server.tools import QueryTools

  async def main():
      context = DbContext(DbContextOptions(connection_string='sqlite+aiosqlite:///:memory:'))
      meta = MetaData()
      users = Table('users', meta, Column('id', Integer, primary_key=True), Column('name', String))
      def seed(conn):
          meta.create_all(conn)
          conn.execute(users.insert(), [{'id': 1, 'name': 'Ada'}])
      async with context.engine.begin() as conn:
          await conn.run_sync(seed)
      tool = Tool.from_function(QueryTools(SqlAlchemyRepository(context)).get_list_records)
      print(await tool.run({'query': {'table': 'users', 'columns': ['id', 'name']}}, None))
      await context.dispose()

  asyncio.run(main())
  '@
  ```

  Observed (the adapter path end to end, with no file written to disk):

  ```text
  {'status': 'ok', 'columns': {'id': 'integer', 'name': 'text'}, 'records': [{'id': 1, 'name': 'Ada'}]}
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
- New modules may still be untracked; run `git status` before assuming a file is under version
  control.
