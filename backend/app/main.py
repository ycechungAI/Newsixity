"""FastAPI application entrypoint.

Stage 0 skeleton: wires the lifespan (DB init + a guarded slot where the
background schedulers will start in Stage 7) and exposes /api/health. Routers,
StaticFiles for the built SPA, auth, and rate limiting arrive in later stages.
"""

from __future__ import annotations

import logging
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


# Serve static frontend built by Next.js static export (Stage 8).
# The 'out/' directory contains the pre-built SPA (HTML, JS, CSS, images).
static_dir = Path(__file__).parent.parent.parent / "out"


class NextExportStaticFiles(StaticFiles):
    """StaticFiles that serves Next.js static-export clean URLs.

    Next `output: "export"` writes one HTML file per route (``finance.html``,
    ``finance/news.html``), but the app links to *extensionless* URLs
    (``/finance``, ``/finance/news``). Plain StaticFiles 404s those. This
    subclass mirrors what Next's own server / Vercel / nginx `try_files` do:

        1. exact path (assets: JS/CSS/images, and ``/`` -> index.html via html=True)
        2. ``{path}.html``  (clean-URL page: ``/finance`` -> ``finance.html``)
        3. ``404.html``     (Next's exported not-found page), status 404
    """

    async def _try(self, path: str, scope) -> Response | None:
        """Return a served response, or None if the path is missing.

        In html=True mode Starlette *returns* a synthesized 404 (serving
        404.html) rather than raising, so a 404 status also counts as a miss.
        """
        try:
            resp = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return None
            raise
        return None if resp.status_code == 404 else resp

    async def get_response(self, path: str, scope) -> Response:
        # 1. Exact path (assets, and "/" -> index.html via html=True).
        resp = await self._try(path, scope)
        if resp is not None:
            return resp

        # 2. Clean-URL page: "/finance" -> "finance.html".
        if path not in ("", ".", "/") and not path.endswith(".html"):
            resp = await self._try(f"{path}.html", scope)
            if resp is not None:
                return resp

        # 3. Exported 404 page, with a real 404 status.
        not_found = await super().get_response("404.html", scope)
        not_found.status_code = 404
        return not_found


if static_dir.is_dir():
    app.mount("/", NextExportStaticFiles(directory=static_dir, html=True), name="static")
else:
    # Fallback: show a message if frontend build is missing.
    @app.get("/{path:path}")
    async def fallback_to_index(_path: str):
        """Serve a helpful error if the frontend has not been built yet."""
        return JSONResponse(
            {"error": "Frontend not built. Run: npm run build"},
            status_code=503,
        )
