"""FastAPI application entrypoint.

Stage 0 skeleton: wires the lifespan (DB init + a guarded slot where the
background schedulers will start in Stage 7) and exposes /api/health. Routers,
StaticFiles for the built SPA, auth, and rate limiting arrive in later stages.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_db
from app.lib.logger.console import install_console_interceptor
from app.lib.scheduler import start_background_services, stop_background_services
from app.lib.server import RateLimitExceeded, check_api_access

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("newsixity")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    install_console_interceptor()
    init_db()

    if settings.disable_background_services:
        logger.info("Background services disabled by config.")
    else:
        # RSS refresh, summarization, and backup schedulers (APScheduler),
        # replacing src/lib/server/background-services.ts.
        start_background_services()

    yield

    if not settings.disable_background_services:
        stop_background_services()
    logger.info("Shutting down.")


app = FastAPI(title="Newsixity", version="0.1.0", lifespan=lifespan)

# Public API paths bypass auth (port of PUBLIC_API_PATHS in src/proxy.ts).
PUBLIC_API_PATHS = {"/api/health"}


@app.middleware("http")
async def api_access_middleware(request: Request, call_next):
    """Loopback-trust + token + CSRF gate over /api/* (port of src/proxy.ts).

    Non-/api/ paths (docs, SPA static files) pass through untouched.
    """
    path = request.url.path
    if path.startswith("/api/") and path not in PUBLIC_API_PATHS:
        access = check_api_access(request)
        if not access.ok:
            return JSONResponse(
                {"error": access.error or "Unauthorized"},
                status_code=access.status or 401,
            )
    return await call_next(request)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(_request: Request, exc: RateLimitExceeded):
    """Match Node's 429 body shape and Retry-After header exactly."""
    return JSONResponse(
        {"error": "Rate limit exceeded", "retryAfter": exc.retry_after},
        status_code=429,
        headers={"Retry-After": str(exc.retry_after)},
    )


# Wire routers
from app.routers import (
    articles,
    categories,
    console,
    feeds,
    finance,
    health,
    ollama,
    preferences,
    research,
    settings as settings_router,
    summarize,
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(articles.router, prefix="/api", tags=["articles"])
app.include_router(feeds.router, prefix="/api", tags=["feeds"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(preferences.router, prefix="/api", tags=["preferences"])
app.include_router(finance.router, prefix="/api", tags=["finance"])
app.include_router(ollama.router, prefix="/api", tags=["ollama"])
app.include_router(research.router, prefix="/api", tags=["research"])
app.include_router(summarize.router, prefix="/api", tags=["summarize"])
app.include_router(console.router, prefix="/api", tags=["console"])
