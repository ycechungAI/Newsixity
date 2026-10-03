"""Resolving publisher share links to playable media.

PCloud (and similar) hand out a page URL with no file extension, so the
frontend's extension check cannot tell it is video and never mounts a player —
the article rendered as a plain link. These pin the server side that resolves
such a link to the real file, and in particular the security property that
makes doing it server-side necessary rather than convenient: every redirect
hop is re-checked, because a public URL can 302 to 127.0.0.1 and a single
up-front check never sees it.
"""

from __future__ import annotations

import pytest

from app.lib.utils import media_resolve
from app.lib.utils.media_resolve import (
    ShareLinkError,
    is_known_share_host,
    resolve_share_link,
)


@pytest.fixture
def client():
    from starlette.testclient import TestClient

    from app.main import app

    return TestClient(app, base_url="http://localhost")


# A host that really resolves. The SSRF gate resolves every hop, so a fabricated
# CDN hostname would fail the test for the wrong reason — it looks unresolvable,
# not playable.
REAL_HOST = "example.com"


class FakeResponse:
    """Minimal stand-in for what `client.stream()` yields.

    Deliberately only exposes the three things the resolver reads: redirect
    status, Location, and status/content-type. Anything else the real response
    has is not something the code under test may depend on.
    """

    def __init__(self, *, location: str | None = None, status: int = 200, content_type: str = ""):
        self.status_code = status
        self.headers = {"content-type": content_type, **({"location": location} if location else {})}

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeClient:
    def __init__(self, hops: list[FakeResponse]):
        self._hops = list(hops)
        self.requested: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream(self, _method, url, **_kwargs):
        self.requested.append(url)
        if not self._hops:
            raise AssertionError("resolver asked for more hops than the test supplied")
        return self._hops.pop(0)


def _install(monkeypatch, hops):
    client = FakeClient(hops)
    monkeypatch.setattr(
        media_resolve, "httpx", type("H", (), {"Client": lambda **_kw: client})
    )
    return client


class TestShareHostDetection:
    @pytest.mark.parametrize(
        "url",
        [
            "https://my.pcloud.com/publink/show?code=XZabc",
            "https://e.pcloud.link/publink/getlink/abc",
            "https://u.pcloud.link/publink/getlink/abc.mp4?linkcode=x",
            "https://pcloud.link/x",
        ],
    )
    def test_recognises_share_links(self, url):
        assert is_known_share_host(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/video.mp4",
            # A lookalike must not opt itself into the redirect path.
            "https://pcloud.link.evil.example/x",
            "https://notpcloud.com/x",
            "ftp://e.pcloud.link/x",
            "not a url",
            "",
        ],
    )
    def test_rejects_everything_else(self, url):
        assert is_known_share_host(url) is False


class TestResolvesToMedia:
    def test_follows_a_redirect_to_a_video(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(status=302, location=f"https://{REAL_HOST}/video.mp4"),
            FakeResponse(content_type="video/mp4"),
        ])

        media = resolve_share_link("https://my.pcloud.com/publink/show?code=XZabc")

        assert media.url == f"https://{REAL_HOST}/video.mp4"
        assert media.content_type == "video/mp4"

    def test_resolves_a_share_link_that_already_ends_in_mp4(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="video/mp4")])

        media = resolve_share_link("https://e.pcloud.link/publink/getlink/abc.mp4")

        assert media.url == "https://e.pcloud.link/publink/getlink/abc.mp4"

    def test_accepts_hls_manifests(self, monkeypatch):
        """Safari plays HLS natively; refusing it would be needlessly lossy."""
        _install(monkeypatch, [FakeResponse(content_type="application/vnd.apple.mpegurl")])

        assert resolve_share_link("https://my.pcloud.com/publink/show?code=XZ").content_type == (
            "application/vnd.apple.mpegurl"
        )

    def test_strips_content_type_parameters(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="video/mp4; charset=utf-8")])

        assert resolve_share_link("https://my.pcloud.com/publink/show?code=XZ").content_type == "video/mp4"


class TestRefusesNonVideo:
    def test_a_web_page_is_not_a_video(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="text/html")])

        with pytest.raises(ShareLinkError, match="web page"):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_a_folder_share_is_not_a_video(self, monkeypatch):
        """PCloud share links point at folders as often as at files."""
        _install(monkeypatch, [FakeResponse(content_type="application/json")])

        with pytest.raises(ShareLinkError, match="not a video"):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_an_error_status_is_reported_with_its_code(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(status=404, content_type="text/html")])

        with pytest.raises(ShareLinkError, match="404"):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_a_redirect_loop_is_bounded(self, monkeypatch):
        # Every hop redirects; the resolver must stop rather than spin.
        hops = [FakeResponse(status=302, location="https://my.pcloud.com/loop") for _ in range(20)]
        _install(monkeypatch, hops)

        with pytest.raises(ShareLinkError, match="redirects too many times"):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_a_redirect_without_a_location_is_refused(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(status=302)])

        with pytest.raises(ShareLinkError, match="redirects nowhere"):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")


class TestSsrfGate:
    """The reason this lives on the server at all."""

    def test_a_hop_to_a_private_address_is_refused(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(status=302, location="http://127.0.0.1/admin"),
            FakeResponse(content_type="video/mp4"),
        ])

        with pytest.raises(ShareLinkError):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_a_hop_to_a_private_hostname_is_refused(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(status=302, location="http://localhost:8000/admin"),
        ])

        with pytest.raises(ShareLinkError):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_a_non_http_scheme_is_refused(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(status=302, location="file:///etc/passwd"),
        ])

        with pytest.raises(ShareLinkError):
            resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

    def test_the_entry_url_is_gated_too(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="video/mp4")])

        with pytest.raises(ShareLinkError):
            resolve_share_link("http://127.0.0.1/video.mp4")

    def test_a_relative_redirect_resolves_against_the_current_hop(self, monkeypatch):
        client = _install(monkeypatch, [
            FakeResponse(status=302, location="/final/video.mp4"),
            FakeResponse(content_type="video/mp4"),
        ])

        media = resolve_share_link("https://my.pcloud.com/publink/show?code=XZ")

        assert client.requested[1] == "https://my.pcloud.com/final/video.mp4"
        assert media.url == "https://my.pcloud.com/final/video.mp4"

    def test_the_media_body_is_never_read(self, monkeypatch):
        """Only headers are needed; buffering a large file would be a bug.

        FakeResponse exposes no body at all, so any read of one raises — which
        is the assertion.
        """
        _install(monkeypatch, [FakeResponse(content_type="video/mp4")])

        assert resolve_share_link("https://my.pcloud.com/publink/show?code=XZ").url


class TestRoute:
    def test_video_link_is_redirected_to(self, client):
        import app.lib.utils.media_resolve as mr

        _install_tests = mr.httpx
        try:
            fake = type(
                "H",
                (),
                {
                    "Client": lambda **_kw: type(
                        "C",
                        (),
                        {
                            "__enter__": lambda s: s,
                            "__exit__": lambda s, *e: False,
                            "stream": lambda s, _m, url, **_k: FakeResponse(
                                content_type="video/mp4"
                            ),
                        },
                    )(),
                },
            )
            mr.httpx = fake
            res = client.get(
                "/api/videos/direct",
                params={"url": "https://my.pcloud.com/publink/show?code=XZ"},
                follow_redirects=False,
            )
            assert res.status_code == 307, res.text
            assert res.headers["location"] == "https://my.pcloud.com/publink/show?code=XZ"
        finally:
            mr.httpx = _install_tests

    def test_a_web_page_share_is_404_with_a_reason(self, client):
        import app.lib.utils.media_resolve as mr

        original = mr.httpx
        try:
            mr.httpx = type(
                "H",
                (),
                {
                    "Client": lambda **_kw: type(
                        "C",
                        (),
                        {
                            "__enter__": lambda s: s,
                            "__exit__": lambda s, *e: False,
                            "stream": lambda s, _m, url, **_k: FakeResponse(
                                content_type="text/html"
                            ),
                        },
                    )(),
                },
            )
            res = client.get(
                "/api/videos/direct",
                params={"url": "https://my.pcloud.com/publink/show?code=XZ"},
            )
            assert res.status_code == 404
            assert "web page" in res.json()["detail"]
        finally:
            mr.httpx = original

    def test_a_private_address_share_is_404(self, client):
        res = client.get("/api/videos/direct", params={"url": "http://127.0.0.1/v.mp4"})
        assert res.status_code == 404