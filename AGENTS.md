# AGENTS.md

## What this is

Early-stage Python MCP server project. Despite the repo name, there is **no database integration yet**. The codebase uses a `src/` layout with `src/mcp_server.py` containing the `MCPServer` (base class) that encapsulates tools, resources, and startup logic. The entry point is `__main__.py` at the repository root. Treat it as a starting point, not a working server.

## Behavioral guidelines

Hard rules — apply them on every task, no exceptions.

- **Ask before any file-modifying terminal command.** Never run a command that creates, edits, moves, or deletes files without asking the user for permission first.
- **Ask before querying data outside the repository.** Any command that reads or inspects data outside this repository's path requires explicit permission before it runs.
- **Never modify files outside the repository.** Creating, editing, or deleting anything outside this repository is strictly forbidden under any circumstance — this rule has no exception.

## Critical gotchas

- **MCP SDK is v2.3.0 and uses the `MCPServer` API**, e.g. `from mcp.server import MCPServer`. The older `FastMCP` API (`mcp.server.fastmcp`) **does not exist** in this version — most online tutorials and pre-2.x examples will fail. Register with decorators `@mcp.tool()`, `@mcp.resource(...)`, `@mcp.prompt()`.
- **The server wrapper class is defined in `src/mcp_server_wrapper.py` as `MCPServerWrapper`, with `MCPServer` as the primary alias (and `MCPServerBase` kept for backward compatibility)**. The entry point `__main__.py` imports `MCPServer` from `mcp_server_wrapper` and runs the server using the async variants (`run_async()`).
- **Valid transports**: `stdio` (default), `sse`, `streamable-http`. The class provides both synchronous (`run()`) and asynchronous (`run_async()` with `run_stdio_async` / `run_sse_async` / `run_streamable_http_async`) variants.
- **No dependency manifest exists** (no `pyproject.toml`, `requirements.txt`, `setup.py`). Dependencies live only inside `.venv`. If a fresh clone is needed, recreate with `pip install "mcp>=2.3.0"`; if you introduce a manifest, keep it authoritative.

## Environment

- Python 3.14 virtualenv at `.venv` (Windows). Always invoke it explicitly: `.\.venv\Scripts\python.exe ...`
- Key installed packages: `mcp` 2.3.0, `mcp-types`, `pydantic` 2.x, `uvicorn`, `starlette`, `anyio`, `httpx2`.

## Commands

- Run the server: `.\.venv\Scripts\python.exe __main__.py`
- **No test, lint, format, or typecheck tooling is configured.** Do not assume a runner exists; if you add one, document the exact command here.

## Project skills

These skills live under `.opencode/skills/` and are exclusive to this repository. Load the matching one before starting the related task.

- **cicd-basics** — CI/CD fundamentals (GitHub Actions, Docker, blue-green/canary deployments, environment management). Use when setting up pipelines, builds, or deployment workflows.
- **conventional-commits** — Conventional Commits v1.0.0 plus kernel-style commit quality. Use when writing, reviewing, or validating commit messages, choosing a commit type, or generating a CHANGELOG.
- **dotnet-patterns** — Idiomatic C#/.NET patterns, dependency injection, async/await, and maintainability. Use when writing or reviewing C#/.NET code.
- **python-pep8-style** — PEP 8 naming, imports, whitespace, comments/docstrings, and programming recommendations, with the reasoning behind each rule. Use when writing, reviewing, or refactoring Python code, or asking about Python style.
- **readme-writer** — Professional `README.md` structure (title, stack badges, About, concept table, architecture, user vs. developer instructions). Use when creating or rewriting a README.
- **solid** — SOLID principles (SRP/OCP/LSP/ISP/DIP) with warnings against over-application. Use when designing or refactoring object-oriented code.

## Git and repo conventions

- Default branch `main`; remote `ErnestoVegaDev/database-mcp`.
- Only `.gitignore` is currently tracked. `server.py` (legacy) was removed; `opencode.json`, `.opencode/`, and `.atl/` are **gitignored** — they are local-only OpenCode/tooling config and will not be committed.
- Commit style follows Conventional Commits (e.g. `chore(gitignore): ...`).
