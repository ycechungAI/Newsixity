# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Newsixity backend (frozen, packaged for Tauri).

Bundles the FastAPI backend + all integrations (trafilatura, yfinance, ollama,
apscheduler) into a standalone executable. Cross-platform: runs as-is on
macOS, Windows, and Linux (no cross-compiling — each platform freezes its own
binary). The frozen binary includes the built SPA (dist/) and, when present,
a seed database (data/newsixity.db) as bundled data.

Build: pyinstaller newsixity-backend.spec
Output: dist/newsixity-backend/newsixity-backend[.exe] (--onedir mode)
"""

import os

from PyInstaller.utils.hooks import collect_all

# `collect_all=[...]` and `excludedimports=[...]` are NOT real Analysis()
# kwargs (that was a bug in an earlier version of this spec — they got
# silently absorbed with no effect, meaning trafilatura/yfinance were never
# actually collected). The real API is the collect_all() helper function
# below, whose (datas, binaries, hiddenimports) results get merged in.
datas = [
    # Built SPA (index.html, hashed JS/CSS, assets)
    ("../dist", "dist"),
]

# Seed database for first-run population. It's gitignored (contains the
# maintainer's live reading data), so it only exists on machines that have
# actually run the app — e.g. a local packaging build, but not a fresh CI
# checkout. _copy_seed_db_if_first_run() (backend/app/db/init_db.py) already
# handles a missing seed gracefully (warns, starts with an empty DB), so skip
# bundling it entirely rather than failing the build when it's absent.
_seed_db = "../data/newsixity.db"
if os.path.exists(_seed_db):
    datas.append((_seed_db, "data"))
binaries = []
hiddenimports = [
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
]

for pkg in ("trafilatura", "courlan", "justext", "yfinance"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["run_server.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude dev/test dependencies that would bloat the bundle
        "pytest",
        "ruff",
        "watchfiles",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# exclude_binaries=True is what makes this an --onedir build: EXE writes just
# the bootloader here, and COLLECT (below) assembles it plus everything else
# into dist/newsixity-backend/. Without this flag, EXE bundles everything
# into a single onefile executable at that same dist/newsixity-backend path
# — which then collides with COLLECT trying to create a directory there
# instead, which was the root cause of this spec's earlier build failure.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="newsixity-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
