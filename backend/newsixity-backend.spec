# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Newsixity backend (frozen, packaged for Tauri).

Bundles the FastAPI backend + all integrations (trafilatura, yfinance, ollama,
apscheduler) into a standalone executable for macOS. The frozen binary includes
the built SPA (dist/) and a seed database (data/newsixity.db) as bundled data.

Build: pyinstaller newsixity-backend.spec
Output: dist/newsixity-backend/newsixity-backend (--onedir mode)
"""

a = Analysis(
    ["run_server.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Built SPA (index.html, hashed JS/CSS, assets)
        ("../dist", "dist"),
        # Seed database for first-run population
        ("../data/newsixity.db", "data"),
    ],
    hiddenimports=[
        # APScheduler: job stores, executors, triggers (lazy-imported)
        "apscheduler.jobstores.memory",
        "apscheduler.executors.asyncio",
        "apscheduler.triggers.interval",
        "apscheduler.triggers.cron",
        # Uvicorn: event loop, protocol, and lifespan selection (lazy CLI parsing)
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[
        # Exclude dev/test dependencies that would bloat the bundle
        "pytest",
        "ruff",
        "watchfiles",
    ],
    noarchive=False,
    collect_all=[
        # Trafilatura (web scraping): content extractors, parsers, data files
        "trafilatura",
        "courlan",
        "justext",
        # yfinance (stock quotes): Yahoo API integrations, data processing
        "yfinance",
    ],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="newsixity-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="newsixity-backend",
)
