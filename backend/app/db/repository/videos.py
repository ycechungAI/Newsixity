"""Persistent YouTube playlist cache.

Replaces the in-process dict in ``app.lib.utils.video``. Playlists are scraped
by pulling ~2 MB per round and change rarely, but a process-local cache went
cold on every restart, which is what made the "Video unavailable" placeholder
visible for as long as the fetch took.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import YoutubePlaylistCache as YoutubePlaylistCacheModel
from app.db.session import SessionLocal

logger = logging.getLogger("newsixity")

# 6 hours, matching the TTL the in-process cache used. Long enough that
# playlists effectively never refetch in normal use, short enough that an edit
# made on YouTube shows up the same day.
DEFAULT_PLAYLIST_TTL_SECONDS = 6 * 60 * 60


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


def save_cached_playlist(
    playlist_id: str,
    payload: dict[str, Any],
    ttl_seconds: int = DEFAULT_PLAYLIST_TTL_SECONDS,
) -> None:
    """Store (or overwrite) a playlist payload with an expiry.

    Rewriting rather than ignoring an existing row is deliberate: this is what
    ``force_refresh`` does, so re-saving must revive an expired entry.
    """
    expires_at = _iso(datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds))
    with SessionLocal() as db:
        stmt = (
            sqlite_insert(YoutubePlaylistCacheModel)
            .values(
                playlist_id=playlist_id,
                payload=json.dumps(payload),
                source=str(payload.get("source") or "scrape"),
                item_count=int(payload.get("totalItems") or 0),
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=["playlist_id"],
                set_={
                    "payload": json.dumps(payload),
                    "source": str(payload.get("source") or "scrape"),
                    "item_count": int(payload.get("totalItems") or 0),
                    "expires_at": expires_at,
                },
            )
        )
        db.execute(stmt)
        db.commit()


def get_cached_playlist(playlist_id: str) -> dict[str, Any] | None:
    """Return ``{"payload", "source", "item_count"}`` if a live entry exists.

    An expired row is a miss, not an error. A row whose payload will not parse
    is also a miss: a corrupt cache entry must degrade to a refetch rather than
    take the playlist sidebar down.
    """
    with SessionLocal() as db:
        row = db.execute(
            select(YoutubePlaylistCacheModel).where(
                YoutubePlaylistCacheModel.playlist_id == playlist_id,
                YoutubePlaylistCacheModel.expires_at > _now_iso(),
            )
        ).scalar_one_or_none()

        if row is None:
            return None

        try:
            payload = json.loads(row.payload)
        except (ValueError, TypeError):
            logger.warning(
                "Discarding unreadable playlist cache row for %s", playlist_id
            )
            return None

        return {
            "payload": payload,
            "source": row.source,
            "item_count": row.item_count,
        }


def delete_cached_playlist(playlist_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            delete(YoutubePlaylistCacheModel).where(
                YoutubePlaylistCacheModel.playlist_id == playlist_id
            )
        )
        db.commit()


def purge_expired_playlists() -> int:
    """Drop expired rows. Keeps the table from growing without bound."""
    with SessionLocal() as db:
        result = db.execute(
            delete(YoutubePlaylistCacheModel).where(
                YoutubePlaylistCacheModel.expires_at <= _now_iso()
            )
        )
        db.commit()
        return result.rowcount or 0