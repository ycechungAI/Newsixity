"""Shared test setup.

Two jobs, both about isolation:

1. **Point every test at a throwaway database.** ``NEWSIXITY_DB_PATH`` must be
   set before ``app.db.session`` is imported, because ``engine`` and
   ``SessionLocal`` are module-level singletons bound at import time — setting
   it later has no effect. pytest loads conftest before collecting test
   modules, which is the only reliable window.

   Without this, integration tests that go through TestClient hit the real
   ``data/newsixity.db``. That is bad twice over: it can mutate the
   developer's own reading data, and it makes the suite pass locally while
   failing anywhere that file does not exist. That is exactly what happened —
   the search-route tests passed on a dev machine and failed in CI, where a
   fresh checkout has no database at all.

2. **Create the schema**, so those tests query empty tables instead of
   erroring with "no such table".
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Must happen at import time, before anything imports app.db.session.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="newsixity-tests-"))
os.environ["NEWSIXITY_DB_PATH"] = str(_TMP_DIR / "test.db")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _initialise_test_database():
    """Build the schema once for the whole session.

    Tests that need isolation beyond this (their own rows, their own engine)
    already monkeypatch SessionLocal onto a temp database of their own; this
    only guarantees the default database exists and has tables.
    """
    from app.db.init_db import init_db

    init_db()
    yield
