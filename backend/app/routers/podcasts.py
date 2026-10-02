"""Podcast feed management and episode playback."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import PodcastEpisode, PodcastFeed
from app.db.session import SessionLocal
from app.lib.podcast.parser import (
    extract_podcast_episodes,
    extract_podcast_feed_info,
    fetch_podcast_feed,
)
from app.lib.podcast.refresh import refresh_all_podcasts as refresh_all_podcast_feeds
from app.schemas import (
    PodcastEpisodeSchema,
    PodcastFeedSchema,
    PodcastSubscribeSchema,
)

router = APIRouter()


@router.get("/podcasts", response_model=list[PodcastFeedSchema])
def list_podcasts():
    """List all subscribed podcasts."""
    with SessionLocal() as session:
        stmt = select(PodcastFeed).order_by(PodcastFeed.created_at)
        feeds = session.execute(stmt).scalars().all()
        return feeds


@router.post("/podcasts", response_model=PodcastFeedSchema)
def subscribe_podcast(payload: PodcastSubscribeSchema):
    """Subscribe to a podcast by feed URL."""
    with SessionLocal() as session:
        existing = session.execute(
            select(PodcastFeed).where(PodcastFeed.feed_url == payload.feedUrl)
        ).scalar_one_or_none()

        if existing:
            return existing

        try:
            feed_data = fetch_podcast_feed(payload.feedUrl)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=400, detail="Could not fetch feed")

        # feedparser only sets bozo for XML it managed to start parsing, so a
        # plain HTML page comes back clean-but-empty. Require actual content,
        # matching probe_feed's check in app.lib.integrations.rss.
        entries = feed_data.get("entries", [])
        title = (feed_data.get("feed", {}).get("title") or "").strip()
        if not entries and not title:
            raise HTTPException(
                status_code=400, detail="That URL did not return an RSS or Atom feed"
            )
        if feed_data.bozo and not entries:
            raise HTTPException(status_code=400, detail="Invalid or malformed feed")

        feed_info = extract_podcast_feed_info(feed_data)
        feed = PodcastFeed(
            feed_url=payload.feedUrl,
            title=feed_info["title"],
            description=feed_info["description"],
            author=feed_info["author"],
            site_url=feed_info["site_url"],
            image_url=feed_info["image_url"],
        )
        session.add(feed)
        session.flush()

        episodes = extract_podcast_episodes(feed_data)
        for ep in episodes:
            stmt = (
                sqlite_insert(PodcastEpisode)
                .values(podcast_id=feed.id, **ep)
                .on_conflict_do_nothing()
            )
            session.execute(stmt)

        session.commit()
        session.refresh(feed)
        return feed


@router.delete("/podcasts/{podcast_id}")
def unsubscribe_podcast(podcast_id: int):
    """Unsubscribe from a podcast and delete all its episodes."""
    with SessionLocal() as session:
        feed = session.execute(
            select(PodcastFeed).where(PodcastFeed.id == podcast_id)
        ).scalar_one_or_none()

        if not feed:
            raise HTTPException(status_code=404, detail="Podcast not found")

        session.execute(
            PodcastEpisode.__table__.delete().where(PodcastEpisode.podcast_id == podcast_id)
        )
        session.delete(feed)
        session.commit()

        return {"status": "unsubscribed"}


@router.get("/podcasts/{podcast_id}/episodes", response_model=list[PodcastEpisodeSchema])
def list_episodes(
    podcast_id: int,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """List episodes for a podcast, paginated."""
    with SessionLocal() as session:
        stmt = (
            select(PodcastEpisode)
            .where(PodcastEpisode.podcast_id == podcast_id)
            .order_by(desc(PodcastEpisode.published_at))
            .offset(skip)
            .limit(limit)
        )
        episodes = session.execute(stmt).scalars().all()
        return episodes


@router.patch("/podcasts/{podcast_id}", response_model=PodcastFeedSchema)
def toggle_podcast_favorite(podcast_id: int, body: dict):
    """Toggle podcast show-level favorite."""
    is_favorite = body.get("is_favorite")
    if is_favorite is None:
        raise HTTPException(status_code=400, detail="is_favorite must be provided")

    with SessionLocal() as session:
        feed = session.execute(
            select(PodcastFeed).where(PodcastFeed.id == podcast_id)
        ).scalar_one_or_none()

        if not feed:
            raise HTTPException(status_code=404, detail="Podcast not found")

        feed.is_favorite = 1 if is_favorite else 0
        session.commit()
        session.refresh(feed)
        return feed


@router.patch("/podcasts/episodes/{episode_id}", response_model=PodcastEpisodeSchema)
def update_episode(episode_id: int, body: dict):
    """Update episode favorite status, progress, or played state.

    Note: Client should throttle progress writes to at most once per ~10 seconds
    to avoid hammering SQLite.
    """
    is_favorite = body.get("is_favorite")
    progress_seconds = body.get("progress_seconds")
    is_played = body.get("is_played")

    if is_favorite is None and progress_seconds is None and is_played is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of is_favorite, progress_seconds, or is_played must be provided",
        )

    with SessionLocal() as session:
        episode = session.execute(
            select(PodcastEpisode).where(PodcastEpisode.id == episode_id)
        ).scalar_one_or_none()

        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")

        if is_favorite is not None:
            episode.is_favorite = 1 if is_favorite else 0
        if progress_seconds is not None:
            episode.progress_seconds = progress_seconds
        if is_played is not None:
            episode.is_played = 1 if is_played else 0

        session.commit()
        session.refresh(episode)
        return episode


@router.post("/podcasts/refresh")
def refresh_all_podcasts():
    """Re-fetch all subscribed podcast feeds."""
    return refresh_all_podcast_feeds()
