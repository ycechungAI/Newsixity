"""Persistent YouTube playlist cache (spec of the "Video unavailable" fix).

``fetch_youtube_playlist`` cached playlists in a process-local dict, so every
app restart began cold and the first fetch after a launch was slow. That is
what made the "Video unavailable" flash intermittent: a playlist-only URL
mounts ``/embed/videoseries?list=...`` — a form that never plays — until the
playlist resolves and the frontend swaps in a real video id. A warm cache made
the gap short enough to miss; a cold one made it visible.

These tests pin the persistence layer: a playlist survives a process restart,
the TTL still expires, and ``force_refresh`` still works.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.repository.videos as videos_repo
from app.db.models import Base, YoutubePlaylistCache
from app.db.repository.videos import (
    delete_cached_playlist,
    get_cached_playlist,
    save_cached_playlist,
)


@pytest.fixture
def db_session_factory(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(videos_repo, "SessionLocal", TestSessionLocal)
    return TestSessionLocal


class TestPlaylistCache:
    def test_round_trips_a_playlist(self, db_session_factory):
        payload = {
            "items": [
                {"title": "First", "videoId": "aaa", "url": "https://y/aaa"},
                {"title": "Second", "videoId": "bbb", "url": "https://y/bbb"},
            ],
            "totalItems": 2,
            "source": "scrape",
        }
        save_cached_playlist("PL123", payload, ttl_seconds=3600)

        cached = get_cached_playlist("PL123")
        assert cached is not None
        assert cached["payload"]["totalItems"] == 2
        assert [i["videoId"] for i in cached["payload"]["items"]] == ["aaa", "bbb"]
        # The source degrades to "rss" on a partial scrape and the caller
        # needs to know which it got.
        assert cached["payload"]["source"] == "scrape"

    def test_miss_returns_none(self, db_session_factory):
        assert get_cached_playlist("PL-nope") is None

    def test_expired_entry_is_not_returned(self, db_session_factory):
        """A stale entry must behave as a miss, not be served."""
        save_cached_playlist(
            "PL-old", {"items": [], "totalItems": 0, "source": "scrape"},
            ttl_seconds=-1,
        )
        assert get_cached_playlist("PL-old") is None

    def test_ttl_is_refreshed_on_rewrite(self, db_session_factory):
        save_cached_playlist(
            "PL-x", {"items": [], "totalItems": 1, "source": "scrape"},
            ttl_seconds=-1,
        )
        assert get_cached_playlist("PL-x") is None

        # Re-saving is what force_refresh does; it must revive the entry.
        save_cached_playlist(
            "PL-x", {"items": [], "totalItems": 2, "source": "scrape"},
            ttl_seconds=3600,
        )
        assert get_cached_playlist("PL-x") is not None

    def test_overwrites_previous_payload(self, db_session_factory):
        save_cached_playlist("PL-y", {"items": [], "totalItems": 1, "source": "scrape"})
        save_cached_playlist("PL-y", {"items": [], "totalItems": 9, "source": "rss"})
        assert get_cached_playlist("PL-y")["payload"]["totalItems"] == 9

    def test_delete_clears_the_entry(self, db_session_factory):
        save_cached_playlist("PL-z", {"items": [], "totalItems": 1, "source": "scrape"})
        delete_cached_playlist("PL-z")
        assert get_cached_playlist("PL-z") is None

    def test_delete_of_a_missing_entry_is_a_no_op(self, db_session_factory):
        delete_cached_playlist("PL-absent")  # must not raise

    def test_survives_a_fresh_session(self, db_session_factory):
        """The point of persisting: a new session sees the same data."""
        save_cached_playlist(
            "PL-persist", {"items": [], "totalItems": 3, "source": "scrape"}
        )
        # sessionmaker is not connection-scoped here, but get_cached_playlist
        # opens its own session, so this exercises the read path a restarted
        # process would take.
        first = get_cached_playlist("PL-persist")
        second = get_cached_playlist("PL-persist")
        assert first == second
        assert first["payload"]["totalItems"] == 3

    def test_unicode_titles_survive_the_json_round_trip(self, db_session_factory):
        save_cached_playlist(
            "PL-uni",
            {"items": [{"title": "café — naïve", "videoId": "u", "url": "https://y/u"}],
             "totalItems": 1, "source": "scrape"},
        )
        assert get_cached_playlist("PL-uni")["payload"]["items"][0]["title"] == "café — naïve"

    def test_corrupt_row_is_treated_as_a_miss(self, db_session_factory):
        """A bad row must not take the playlist sidebar down."""
        from app.db.models import YoutubePlaylistCache

        with db_session_factory() as db:
            db.add(
                YoutubePlaylistCache(
                    playlist_id="PL-bad",
                    payload="{not json",
                    source="scrape",
                    item_count=0,
                    expires_at="2099-01-01T00:00:00.000Z",
                )
            )
            db.commit()
        assert get_cached_playlist("PL-bad") is None