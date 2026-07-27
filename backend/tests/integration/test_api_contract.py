"""Every /api/* URL the frontend calls must exist on the backend.

This exists because of a bug class that keeps slipping through: a route the
UI calls is missing or registered under a different method, and *nothing
fails loudly*. The catch-all static route answers with the SPA's index.html
at status 200, the frontend's `res.json()` throws, a `catch` swallows it, and
the feature silently renders empty.

That is how Settings > Feed Rankings shipped broken — it fetched
GET /api/feeds/weights, which only existed as PUT — and how the top-bar
search box submitted to a parameter no route read. Unit tests all passed,
because nothing asserted the endpoints were reachable.

So this walks the actual frontend source, extracts the URLs and methods it
calls, and checks each against FastAPI's route table.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from app.main import app

SRC = Path(__file__).resolve().parents[3] / "src"

# fetch("/api/...", { method: "PATCH" })  — the method arg is optional (GET).
# Handles single/double/backtick quotes; template holes become a wildcard.
_FETCH_RE = re.compile(
    r"""fetch\(\s*[`'"](?P<url>/api/[^`'"]*)[`'"]\s*(?P<rest>,\s*\{.*?\})?""",
    re.DOTALL,
)
_METHOD_RE = re.compile(r"""method\s*:\s*['"](?P<m>[A-Z]+)['"]""")


def _frontend_calls() -> set[tuple[str, str]]:
    """(method, path) pairs the frontend actually calls."""
    calls: set[tuple[str, str]] = set()
    for path in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        for m in _FETCH_RE.finditer(text):
            url = m.group("url").split("?")[0].rstrip("/")
            # `${expr}` interpolation -> a single path segment wildcard.
            url = re.sub(r"\$\{[^}]*\}", "{param}", url)
            method = "GET"
            if m.group("rest"):
                found = _METHOD_RE.search(m.group("rest"))
                if found:
                    method = found.group("m")
            calls.add((method, url))
    return calls


def _backend_paths() -> dict[str, set[str]]:
    """Full path -> methods, read from the OpenAPI schema.

    Deliberately not walking app.routes: this FastAPI version wraps included
    routers in an internal _IncludedRouter whose nested paths exclude their
    prefix, so reassembling them means depending on private structure that
    changes between versions. The schema is public and already resolved.
    """
    schema = app.openapi()
    return {
        path: {m.upper() for m in ops if m.lower() in
               {"get", "post", "put", "patch", "delete", "head", "options"}}
        for path, ops in schema["paths"].items()
    }


def _backend_routes() -> list[tuple[set[str], re.Pattern]]:
    routes = []
    for path, methods in _backend_paths().items():
        # {article_id} -> match any single segment.
        pattern = re.sub(r"\{[^}]+\}", r"[^/]+", path.rstrip("/"))
        routes.append((methods, re.compile(f"^{pattern}$")))
    return routes


def _is_served(method: str, url: str, routes) -> bool:
    # A frontend "{param}" hole can be any segment, so treat it as a wildcard
    # on both sides rather than requiring a literal match.
    probe = url.replace("{param}", "X")
    return any(method in methods and rx.match(probe) for methods, rx in routes)


class TestFrontendApiCallsAreServed:
    def test_the_scanner_actually_finds_calls(self):
        """Guard the guard: a broken regex would make this suite vacuous."""
        calls = _frontend_calls()
        assert len(calls) > 15, f"only found {len(calls)} API calls — regex likely broken"

    @pytest.mark.parametrize("call", sorted(_frontend_calls()))
    def test_endpoint_exists(self, call):
        method, url = call
        routes = _backend_routes()
        assert _is_served(method, url, routes), (
            f"Frontend calls {method} {url} but no backend route serves it. "
            f"This does NOT fail at runtime — the static catch-all returns "
            f"index.html with status 200 and the feature silently renders empty."
        )


class TestKnownRegressions:
    """Endpoints that shipped broken once; pinned so they cannot regress."""

    def test_feed_weights_supports_get_and_patch(self):
        routes = _backend_routes()
        # Settings > Feed Rankings reads with GET and saves with PATCH.
        assert _is_served("GET", "/api/feeds/weights", routes)
        assert _is_served("PATCH", "/api/feeds/weights", routes)

    def test_article_search_is_not_shadowed_by_the_id_route(self):
        """/articles/search must be declared before /articles/{article_id}.

        FastAPI matches in definition order, so the reverse order makes
        "search" parse as an article id and 422.
        """
        paths = list(_backend_paths())
        assert "/api/articles/search" in paths
        assert paths.index("/api/articles/search") < paths.index("/api/articles/{article_id}")

    def test_no_route_repeats_the_api_prefix(self):
        """Routers are included with prefix='/api'; repeating it yields /api/api/*."""
        bad = [p for p in _backend_paths() if p.startswith("/api/api")]
        assert bad == [], f"double-prefixed routes: {bad}"
