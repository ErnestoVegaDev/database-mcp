# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for the database-mcp stdio server.

Build with:  .\\.venv\\Scripts\\pyinstaller.exe database-mcp.spec

Three things about this project force the collects below, because PyInstaller
cannot see them by static analysis:

* ``pathex=['src']`` - the slices import absolutly from the top of ``src/``
  (``features.*``, ``shared.*``), so ``src`` must be a package root at build
  time. Without it the analysis finds no project module at all.
* SQLAlchemy resolves its dialect modules from a URL string at runtime, so the
  ``postgresql.asyncpg`` and ``mysql.aiomysql`` dialects are never imported in
  source. They are declared as hidden imports, and ``collect_all`` brings the
  dialect packages and their data along.
* ``asyncpg`` and ``aiomysql`` ship compiled extensions, which ``collect_all``
  gathers so the frozen binary has the actual driver code, not just the
  SQLAlchemy dialect that wraps it.

``console=True`` is required: this is a stdio MCP server, so stdout carries the
JSON-RPC stream and stderr carries diagnostics. A windowed build would break it.
"""

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    "sqlalchemy.dialects.postgresql.asyncpg",
    "sqlalchemy.dialects.mysql.aiomysql",
]

for package in ("sqlalchemy", "asyncpg", "aiomysql"):
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]


a = Analysis(  # noqa: F821 - provided by PyInstaller at build time
    ["__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="database-mcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
