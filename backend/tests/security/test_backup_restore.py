"""Security/correctness tests for backup listing and the restore integrity gate.

Covers app/lib/backup/restore.py (validation gate, staged apply, path
traversal) and the /api/console/backups* routes in app/routers/console.py.
Every test isolates the "live DB" behind settings.resolve_db_path() to a
pytest tmp_path so nothing here can touch the real repo data/ directory.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings as app_settings
from app.lib.backup.restore import (
    KNOWN_SCHEMA_OBJECTS,
    BackupValidationError,
    _validate_sqlite_file,
    apply_pending_restore,
    list_backups,
    stage_restore_from_bytes,
    stage_restore_from_existing,
)

CORE_TABLES_SQL = """
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE feeds (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT);
CREATE TABLE settings (id INTEGER PRIMARY KEY, key TEXT);
"""


def _make_valid_db(path: Path) -> None:
    """Write a minimal but genuine SQLite file with the core Newsixity tables."""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(CORE_TABLES_SQL)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    """Point settings.resolve_db_path() at an isolated temp dir for this test.

    ``settings`` is a module-level singleton imported by reference everywhere
    (app.lib.backup.restore, app.routers.console, ...), so patching the bound
    method on this one object redirects every consumer.
    """
    db_path = tmp_path / "newsixity.db"
    # `settings` is a pydantic BaseSettings instance — its __setattr__ only
    # accepts declared fields, so the method is patched on the class instead
    # (there is only ever one Settings instance, so this is equivalent to
    # patching the singleton for the duration of the test).
    monkeypatch.setattr(type(app_settings), "resolve_db_path", lambda self: db_path)
    return db_path


class TestListBackups:
    def test_empty_dir_returns_empty_list(self, db_env):
        assert list_backups() == []

    def test_filters_by_db_suffix_and_classifies_auto_vs_manual(self, db_env):
        backups_dir = db_env.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        (backups_dir / "newsixity-2024-01-01T00-00-00.db").write_bytes(b"x")
        (backups_dir / "newsixity-auto-2024-01-01T00-00-00.db").write_bytes(b"x")
        # Non-.db noise that lives in the same directory in production.
        (backups_dir / "newsixity-2024-01-01T00-00-00.db-journal").write_bytes(b"x")
        (backups_dir / ".DS_Store").write_bytes(b"x")

        items = list_backups()
        names = {b["name"] for b in items}
        assert names == {
            "newsixity-2024-01-01T00-00-00.db",
            "newsixity-auto-2024-01-01T00-00-00.db",
        }

        by_name = {b["name"]: b for b in items}
        assert by_name["newsixity-2024-01-01T00-00-00.db"]["type"] == "manual"
        assert by_name["newsixity-auto-2024-01-01T00-00-00.db"]["type"] == "auto"
        for item in items:
            assert "size" in item and "mtime" in item


class TestValidationGateRejectsBadInput:
    def test_rejects_non_sqlite_file(self, db_env):
        with pytest.raises(BackupValidationError):
            stage_restore_from_bytes(b"this is definitely not a sqlite database" * 4)

    def test_rejects_corrupted_file_with_valid_header_but_garbage_body(self, db_env):
        # Passes the magic-header check but is not openable/valid SQLite.
        data = b"SQLite format 3\x00" + b"\xff" * 256
        with pytest.raises(BackupValidationError):
            stage_restore_from_bytes(data)

    def test_rejects_oversized_upload(self, db_env, monkeypatch):
        monkeypatch.setattr("app.lib.backup.restore.MAX_RESTORE_UPLOAD_BYTES", 10)
        with pytest.raises(BackupValidationError) as exc_info:
            stage_restore_from_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
        assert exc_info.value.status_code == 413

    def test_rejects_valid_sqlite_missing_core_newsixity_tables(self, db_env, tmp_path):
        p = tmp_path / "not-newsixity.db"
        conn = sqlite3.connect(str(p))
        conn.execute("CREATE TABLE some_other_table (id INTEGER)")
        conn.commit()
        conn.close()

        with pytest.raises(BackupValidationError):
            stage_restore_from_bytes(p.read_bytes())

    def test_live_db_untouched_when_upload_rejected(self, db_env):
        _make_valid_db(db_env)
        original = db_env.read_bytes()

        with pytest.raises(BackupValidationError):
            stage_restore_from_bytes(b"not a database at all")

        assert db_env.read_bytes() == original
        assert not (db_env.parent / "pending-restore.db").exists()


class TestValidationGateAcceptsGoodInput:
    def test_accepts_valid_backup_and_stages_it(self, db_env, tmp_path):
        candidate = tmp_path / "valid.db"
        _make_valid_db(candidate)

        result = stage_restore_from_bytes(candidate.read_bytes())

        assert result["staged"] is True
        pending = db_env.parent / "pending-restore.db"
        assert pending.is_file()
        # The staged file really is the validated candidate, not garbage.
        conn = sqlite3.connect(str(pending))
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert {"articles", "categories", "feeds", "settings"} <= tables

    def test_stages_existing_backup_by_name_without_deleting_original(self, db_env):
        backups_dir = db_env.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backups_dir / "newsixity-2024-01-01T00-00-00.db"
        _make_valid_db(backup_path)

        result = stage_restore_from_existing("newsixity-2024-01-01T00-00-00.db")

        assert result["staged"] is True
        assert backup_path.is_file(), "restoring by name must not consume the original backup"
        assert (db_env.parent / "pending-restore.db").is_file()


class TestPathTraversalRejected:
    def test_rejects_parent_directory_traversal(self, db_env):
        with pytest.raises(BackupValidationError):
            stage_restore_from_existing("../newsixity.db")

    def test_rejects_nested_traversal(self, db_env):
        with pytest.raises(BackupValidationError):
            stage_restore_from_existing("subdir/../../newsixity.db")

    def test_rejects_absolute_path(self, db_env):
        with pytest.raises(BackupValidationError):
            stage_restore_from_existing("/etc/passwd")

    def test_rejects_bare_dotdot(self, db_env):
        with pytest.raises(BackupValidationError):
            stage_restore_from_existing("..")

    def test_rejects_windows_style_separator(self, db_env):
        with pytest.raises(BackupValidationError):
            stage_restore_from_existing("..\\newsixity.db")

    def test_nonexistent_name_is_404_not_traversal(self, db_env):
        backups_dir = db_env.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(BackupValidationError) as exc_info:
            stage_restore_from_existing("does-not-exist.db")
        assert exc_info.value.status_code == 404


class TestApplyPendingRestore:
    def test_noop_when_no_pending_file(self, db_env):
        _make_valid_db(db_env)
        original = db_env.read_bytes()

        apply_pending_restore()  # must not raise

        assert db_env.read_bytes() == original

    def test_swaps_pending_db_into_place_and_takes_safety_copy(self, db_env, tmp_path):
        _make_valid_db(db_env)
        # Mark the live DB so the safety copy can be identified by content.
        # (Not by bytes: the safety copy is written with VACUUM INTO, which
        # produces an equivalent but not byte-identical file.)
        conn = sqlite3.connect(str(db_env))
        conn.execute("INSERT INTO categories (id, name) VALUES (111, 'original-marker')")
        conn.commit()
        conn.close()

        # Build a distinguishable "new" DB and stage it as pending-restore.db.
        new_db = tmp_path / "new.db"
        _make_valid_db(new_db)
        conn = sqlite3.connect(str(new_db))
        conn.execute("INSERT INTO categories (id, name) VALUES (999, 'restored-marker')")
        conn.commit()
        conn.close()

        pending = db_env.parent / "pending-restore.db"
        shutil.copy2(new_db, pending)

        apply_pending_restore()

        assert not pending.exists(), "pending file must be consumed"

        conn = sqlite3.connect(str(db_env))
        row = conn.execute(
            "SELECT name FROM categories WHERE id = 999"
        ).fetchone()
        conn.close()
        assert row == ("restored-marker",), "live DB must now be the restored content"

        backups_dir = db_env.parent / "backups"
        safety_copies = list(backups_dir.glob("pre-restore-*.db"))
        assert len(safety_copies) == 1, "exactly one safety copy of the prior DB must exist"

        # The safety copy must hold the *pre-restore* content, not the restored one.
        conn = sqlite3.connect(str(safety_copies[0]))
        names = {r[0] for r in conn.execute("SELECT name FROM categories").fetchall()}
        conn.close()
        assert "original-marker" in names
        assert "restored-marker" not in names

    def test_safety_copy_name_is_immune_to_backup_pruning(self, db_env, tmp_path):
        """The safety copy must not be deletable by the manual-backup pruner.

        console.py's _cleanup_old_backups() prunes everything matching
        "newsixity-" down to MAX_BACKUPS (2). Naming the safety copy
        "newsixity-pre-restore-..." would put the one file that can undo a
        bad restore into that pool, where two manual backups would evict it.
        """
        from app.lib.backup.restore import SAFETY_PREFIX, BACKUP_PREFIX

        assert not SAFETY_PREFIX.startswith(BACKUP_PREFIX)

        _make_valid_db(db_env)
        pending = db_env.parent / "pending-restore.db"
        _make_valid_db(pending)
        apply_pending_restore()

        safety = next((db_env.parent / "backups").glob("pre-restore-*.db"))
        assert not safety.name.startswith(BACKUP_PREFIX)

    def test_safety_copy_preserves_data_still_in_the_wal(self, db_env):
        """Committed-but-uncheckpointed rows must survive into the safety copy.

        The DB runs in WAL mode, so recent commits sit in the -wal sidecar
        rather than the main file — and apply_pending_restore deletes that
        sidecar right after taking the copy. A plain shutil.copy2 captures
        only the main file, so those commits are lost permanently. This is
        the case where a restore is most likely (an unclean shutdown), which
        is exactly when the safety net has to hold.
        """
        _make_valid_db(db_env)
        # Simulate an unclean shutdown: commit through a WAL connection that
        # is never closed, so nothing is checkpointed into the main file.
        live = sqlite3.connect(str(db_env))
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("INSERT INTO categories (id, name) VALUES (222, 'only-in-wal')")
        live.commit()
        assert Path(str(db_env) + "-wal").stat().st_size > 0, "row must really be in the WAL"

        pending = db_env.parent / "pending-restore.db"
        _make_valid_db(pending)

        apply_pending_restore()
        live.close()

        safety = next((db_env.parent / "backups").glob("pre-restore-*.db"))
        conn = sqlite3.connect(str(safety))
        names = {r[0] for r in conn.execute("SELECT name FROM categories").fetchall()}
        conn.close()
        assert "only-in-wal" in names

    def test_deletes_stale_wal_and_shm_sidecars(self, db_env, tmp_path):
        _make_valid_db(db_env)
        wal = Path(str(db_env) + "-wal")
        shm = Path(str(db_env) + "-shm")
        wal.write_bytes(b"stale-wal-data")
        shm.write_bytes(b"stale-shm-data")

        pending = db_env.parent / "pending-restore.db"
        _make_valid_db(pending)

        apply_pending_restore()

        assert not wal.exists()
        assert not shm.exists()

    def test_failed_safety_copy_aborts_restore_without_touching_live_db(
        self, db_env, monkeypatch
    ):
        _make_valid_db(db_env)
        original = db_env.read_bytes()

        pending = db_env.parent / "pending-restore.db"
        _make_valid_db(pending)

        def _boom(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("app.lib.backup.restore._snapshot_db", _boom)

        apply_pending_restore()  # defensive: must not raise

        assert db_env.read_bytes() == original, "live DB must be untouched if safety copy failed"
        assert pending.is_file(), "pending restore must remain staged for a later retry"


class TestBackupRoutes:
    """Route-level coverage over /api/console/backups*.

    TestClient's Host header must resolve to a loopback host for
    check_api_access's local-trust path (see app/lib/server/auth.py) to admit
    these admin-gated requests without a token.
    """

    @pytest.fixture
    def client(self):
        from app.main import app

        return TestClient(app, base_url="http://localhost")

    def test_list_backups_endpoint(self, db_env, client):
        backups_dir = db_env.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        _make_valid_db(backups_dir / "newsixity-auto-2024-01-01T00-00-00.db")

        resp = client.get("/api/console/backups")
        assert resp.status_code == 200
        data = resp.json()
        assert any(b["name"] == "newsixity-auto-2024-01-01T00-00-00.db" for b in data["backups"])
        assert all(b["type"] in ("auto", "manual", "safety") for b in data["backups"])

    def test_export_downloads_a_restorable_snapshot_of_the_live_db(
        self, db_env, client, tmp_path
    ):
        """Export must round-trip: what comes out must pass the import gate.

        This is the whole point of the feature — carrying the file to another
        machine is only useful if that machine's restore endpoint accepts it.
        """
        _make_valid_db(db_env)
        conn = sqlite3.connect(str(db_env))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO categories (id, name) VALUES (777, 'export-marker')")
        conn.commit()
        # Left open on purpose: the row is still in the WAL, which a plain
        # file copy of newsixity.db would not capture.

        resp = client.get("/api/console/backups/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert "newsixity-export-" in resp.headers["content-disposition"]
        conn.close()

        exported = tmp_path / "carried-to-other-machine.db"
        exported.write_bytes(resp.content)

        # It is a real SQLite DB, and it contains the not-yet-checkpointed row.
        check = sqlite3.connect(str(exported))
        names = {r[0] for r in check.execute("SELECT name FROM categories").fetchall()}
        check.close()
        assert "export-marker" in names

        # And the other machine's import gate accepts it.
        _validate_sqlite_file(exported)

    def test_export_leaves_no_temp_file_behind(self, db_env, client):
        _make_valid_db(db_env)
        resp = client.get("/api/console/backups/export")
        assert resp.status_code == 200
        leftovers = list((db_env.parent / "backups").glob(".export-*.db"))
        assert leftovers == [], f"export temp files not cleaned up: {leftovers}"

    def test_download_returns_an_existing_backup(self, db_env, client):
        backups_dir = db_env.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        target = backups_dir / "newsixity-2024-01-01T00-00-00.db"
        _make_valid_db(target)

        resp = client.get("/api/console/backups/download", params={"name": target.name})
        assert resp.status_code == 200
        assert resp.content == target.read_bytes()

    def test_download_rejects_path_traversal(self, db_env, client):
        for bad in ("../../etc/passwd", "..", "/etc/passwd", "sub/dir.db"):
            resp = client.get("/api/console/backups/download", params={"name": bad})
            assert resp.status_code in (400, 404), f"{bad!r} was not rejected"
            assert "error" in resp.json()

    def test_download_rejects_missing_backup(self, db_env, client):
        resp = client.get("/api/console/backups/download", params={"name": "nope.db"})
        assert resp.status_code == 404

    def test_restore_rejects_path_traversal_name(self, db_env, client):
        resp = client.post("/api/console/backups/restore", params={"name": "../../etc/passwd"})
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_restore_rejects_corrupted_upload_body(self, db_env, client):
        resp = client.post(
            "/api/console/backups/restore",
            content=b"not a real sqlite database",
            headers={"content-type": "application/octet-stream"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
        assert not (db_env.parent / "pending-restore.db").exists()

    def test_restore_stages_valid_upload_body(self, db_env, client, tmp_path):
        candidate = tmp_path / "valid.db"
        _make_valid_db(candidate)

        resp = client.post(
            "/api/console/backups/restore",
            content=candidate.read_bytes(),
            headers={"content-type": "application/octet-stream"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["staged"] is True
        assert (db_env.parent / "pending-restore.db").is_file()

    def test_restore_by_existing_name_stages_it(self, db_env, client):
        backups_dir = db_env.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        _make_valid_db(backups_dir / "newsixity-2024-01-01T00-00-00.db")

        resp = client.post(
            "/api/console/backups/restore",
            params={"name": "newsixity-2024-01-01T00-00-00.db"},
        )
        assert resp.status_code == 200
        assert resp.json()["staged"] is True

    def test_restore_missing_name_and_empty_body_is_400(self, db_env, client):
        resp = client.post("/api/console/backups/restore")
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestSchemaObjectAllowlist:
    """Newsixity's own FTS5 triggers must not be reported as suspicious.

    A warning that fires on every legitimate restore is worse than no
    warning: it trains the reader to ignore the one message that is supposed
    to flag a hostile file's triggers/views.
    """

    def _db_with_triggers(self, path, names):
        conn = sqlite3.connect(str(path))
        conn.executescript(CORE_TABLES_SQL)
        for n in names:
            conn.execute(
                f"CREATE TRIGGER {n} AFTER INSERT ON articles BEGIN "
                f"UPDATE articles SET title=title WHERE id=new.id; END"
            )
        conn.commit()
        conn.close()

    def test_own_fts5_triggers_are_not_flagged(self, db_env, tmp_path, caplog):
        path = tmp_path / "with_fts.db"
        self._db_with_triggers(path, KNOWN_SCHEMA_OBJECTS)

        with caplog.at_level("WARNING"):
            _validate_sqlite_file(path)  # must not raise

        assert "unexpected triggers" not in caplog.text.lower()

    def test_foreign_triggers_are_still_flagged(self, db_env, tmp_path, caplog):
        path = tmp_path / "with_foreign.db"
        self._db_with_triggers(path, ["evil_trigger"])

        with caplog.at_level("WARNING"):
            _validate_sqlite_file(path)

        assert "evil_trigger" in caplog.text
