"""FastAPI application entrypoint.

Stage 0 skeleton: wires the lifespan (DB init + a guarded slot where the
background schedulers will start in Stage 7) and exposes /api/health. Routers,
StaticFiles for the built SPA, auth, and rate limiting arrive in later stages.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

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
    podcasts,
    preferences,
    research,
    settings as settings_router,
    summarize,
    videos,
    weather,
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
app.include_router(podcasts.router, prefix="/api", tags=["podcasts"])
app.include_router(videos.router, prefix="/api", tags=["videos"])
app.include_router(weather.router, prefix="/api", tags=["weather"])
app.include_router(console.router, prefix="/api", tags=["console"])


# Serve the SPA built by Vite (`npm run build`).
# The 'dist/' directory contains the pre-built app (index.html, hashed JS/CSS,
# public/ assets). Vite emits a single index.html — client-side routing
# (React Router) owns every other path.
# In frozen (PyInstaller) mode, resolve against the bundle's sys._MEIPASS.
if getattr(sys, "frozen", False):
    # PyInstaller unpacks to a temporary directory stored in sys._MEIPASS.
    static_dir = Path(sys._MEIPASS) / "dist"  # type: ignore[attr-defined]
else:
    static_dir = Path(__file__).parent.parent.parent / "dist"


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for unmatched paths.

    A path StaticFiles can't resolve to a real file (e.g. ``/finance``,
    ``/article/123``) isn't necessarily invalid — it's a client-side route.
    Serve index.html with a 200 so React Router mounts and decides for
    itself whether to render a page or its own NotFoundPage, mirroring the
    standard SPA-fallback pattern (nginx `try_files`, Vercel rewrites, etc).
    """

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


if static_dir.is_dir():
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")
else:
    # Fallback: show a message if frontend build is missing.
    @app.get("/{path:path}")
    async def fallback_to_index(_path: str):
        """Serve a helpful error if the frontend has not been built yet."""
        return JSONResponse(
            {"error": "Frontend not built. Run: npm run build"},
            status_code=503,
        )
