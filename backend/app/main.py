"""FastAPI application entrypoint.

Stage 0 skeleton: wires the lifespan (DB init + a guarded slot where the
background schedulers will start in Stage 7) and exposes /api/health. Routers,
StaticFiles for the built SPA, auth, and rate limiting arrive in later stages.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("newsixity")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()

    if settings.disable_background_services:
        logger.info("Background services disabled by config.")
    else:
        # Stage 7: start RSS refresh, summarization, and backup schedulers here
        # (APScheduler), replacing src/lib/server/background-services.ts.
        logger.info("Background services slot ready (schedulers wired in Stage 7).")

    yield

    logger.info("Shutting down.")


app = FastAPI(title="Newsixity", version="0.1.0", lifespan=lifespan)

# Wire routers
from app.routers import health, categories, articles, feeds

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(articles.router, prefix="/api", tags=["articles"])
app.include_router(feeds.router, prefix="/api", tags=["feeds"])
