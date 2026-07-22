"""Static entrypoint for the frozen (PyInstaller) backend.

The dev workflow uses ``uvicorn app.main:app --reload`` (a CLI string that
imports the app lazily). PyInstaller can't follow that string, so the packaged
build uses this module as its single, static entrypoint: it imports the app
object directly and starts uvicorn programmatically.

Host/port come from the environment (``NEWSIXITY_HOST`` / ``NEWSIXITY_PORT``),
which the Tauri shell sets when it spawns this binary as a sidecar. Defaults
match the dev server so running this script directly still works.
"""

from __future__ import annotations

import os

import uvicorn

from app.main import app


def main() -> None:
    host = os.environ.get("NEWSIXITY_HOST", "127.0.0.1")
    port = int(os.environ.get("NEWSIXITY_PORT", "8000"))
    # No --reload / watchfiles in the frozen build (dev-only, and unfreezable).
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
