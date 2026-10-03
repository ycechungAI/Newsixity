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
    classify_share_link,
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

    Deliberately only exposes what the resolver reads: redirect status,
    Location, status/content-type, and the framing headers.
    """

    def __init__(
        self,
        *,
        location: str | None = None,
        status: int = 200,
        content_type: str = "",
        headers: dict | None = None,
    ):
        self.status_code = status
        self.headers = {
            "content-type": content_type,
            **({"location": location} if location else {}),
            **(headers or {}),
        }

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
        """The strict resolver still refuses a page — it only returns files.

        Its caller-facing sibling is what the UI uses; see
        TestClassifyShareLink, where a page is the folder-browser case rather
        than an error. Keeping both is the point: one asks "is this playable?",
        the other asks "what is this, and can I show it?".
        """
        _install(monkeypatch, [FakeResponse(content_type="text/html")])

        with pytest.raises(ShareLinkError, match="not a playable video"):
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


class TestClassifyShareLink:
    """A folder share is a *page*, not a failure.

    This is the PCloud case: the link opens a window listing the videos, the
    user picks one, it plays. The UI needs to know that is what it is looking
    at, and needs to know whether it may be framed — a refused frame renders as
    a blank box with no error anywhere.
    """

    def test_a_folder_listing_is_a_page_not_a_refusal(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="text/html; charset=utf-8")])

        result = classify_share_link("https://u.pcloud.link/publink/show?code=XZ")

        assert result.kind == "page", result
        assert result.reason is None

    def test_a_redirected_share_reports_the_url_to_load(self, monkeypatch):
        """my.pcloud.com 302s to u.pcloud.link; the frame must load *that*."""
        _install(monkeypatch, [
            FakeResponse(status=302, location="https://u.pcloud.link/publink/show?code=XZ"),
            FakeResponse(content_type="text/html"),
        ])

        result = classify_share_link("https://my.pcloud.com/publink/show?code=XZ")

        assert result.kind == "page"
        assert result.url == "https://u.pcloud.link/publink/show?code=XZ"

    def test_a_page_with_no_x_frame_options_is_framable(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="text/html")])

        assert classify_share_link("https://u.pcloud.link/publink/show?code=XZ").framable is True

    def test_sameorigin_is_not_framable_for_us(self, monkeypatch):
        """Measured on PCloud's own e.pcloud.link: X-Frame-Options: SAMEORIGIN.

        From a 127.0.0.1 origin that is a refusal, so offering a frame would
        show an empty box.
        """
        _install(monkeypatch, [
            FakeResponse(content_type="text/html", headers={"x-frame-options": "SAMEORIGIN"})
        ])

        result = classify_share_link("https://e.pcloud.link/publink/show?code=XZ")

        assert result.kind == "page"
        assert result.framable is False

    def test_a_csp_frame_ancestors_none_blocks_framing(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(
                content_type="text/html",
                headers={"content-security-policy": "default-src 'self'; frame-ancestors 'none'"},
            )
        ])

        assert classify_share_link("https://u.pcloud.link/x").framable is False

    def test_a_csp_frame_ancestors_self_blocks_us(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(
                content_type="text/html",
                headers={"content-security-policy": "frame-ancestors 'self'"},
            )
        ])

        assert classify_share_link("https://u.pcloud.link/x").framable is False

    def test_a_csp_frame_ancestors_wildcard_permits_framing(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(
                content_type="text/html",
                headers={"content-security-policy": "frame-ancestors *"},
            )
        ])

        assert classify_share_link("https://u.pcloud.link/x").framable is True

    def test_allow_from_is_not_treated_as_permission(self, monkeypatch):
        """Deprecated and ignored by every current browser.

        Honouring it would put the blank frame straight back.
        """
        _install(monkeypatch, [
            FakeResponse(
                content_type="text/html",
                headers={"x-frame-options": "ALLOW-FROM https://example.com"},
            )
        ])

        assert classify_share_link("https://u.pcloud.link/x").framable is False

    def test_media_carries_no_framable_verdict(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="video/mp4")])

        result = classify_share_link("https://e.pcloud.link/publink/getlink/a.mp4")

        assert result.kind == "media"
        assert result.framable is None, "a file is played, not framed"

    def test_a_json_api_is_still_a_refusal(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(content_type="application/json")])

        result = classify_share_link("https://my.pcloud.com/publink/show?code=XZ")

        assert result.kind == "refused"
        assert "not a video" in result.reason

    def test_an_error_page_is_refused_with_its_status(self, monkeypatch):
        _install(monkeypatch, [FakeResponse(status=404, content_type="text/html")])

        result = classify_share_link("https://u.pcloud.link/publink/show?code=GONE")

        assert result.kind == "refused"
        assert "404" in result.reason

    def test_a_private_hop_is_refused_rather_than_classified(self, monkeypatch):
        _install(monkeypatch, [
            FakeResponse(status=302, location="http://127.0.0.1/admin"),
        ])

        with pytest.raises(ShareLinkError):
            classify_share_link("https://my.pcloud.com/publink/show?code=XZ")


class TestRoute:
    """The route answers JSON, never a bare 404 or a silent 307.

    A 307 handed to `<video src>` fails invisibly — a dead player with nothing
    in any log. The response has to carry the reason so the UI can offer a real
    alternative instead of showing nothing useful.
    """

    def _fake_httpx(self, content_type):
        return type(
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
                            content_type=content_type
                        ),
                    },
                )(),
            },
        )

    def test_a_playable_share_reports_its_url(self, client, monkeypatch):
        import app.lib.utils.media_resolve as mr

        monkeypatch.setattr(mr, "httpx", self._fake_httpx("video/mp4"))

        body = client.get(
            "/api/videos/resolve",
            params={"url": "https://my.pcloud.com/publink/show?code=XZ"},
        ).json()

        assert body["kind"] == "media"
        assert body["playable"] is True
        assert body["contentType"] == "video/mp4"
        assert body["reason"] is None

    def test_a_folder_share_reports_kind_page_and_framability(self, client, monkeypatch):
        """The UI branches on exactly these two fields."""
        import app.lib.utils.media_resolve as mr

        monkeypatch.setattr(mr, "httpx", self._fake_httpx("text/html"))

        body = client.get(
            "/api/videos/resolve",
            params={"url": "https://u.pcloud.link/publink/show?code=XZ"},
        ).json()

        assert body["kind"] == "page"
        assert body["playable"] is False, "a page is browsed, not played"
        assert body["framable"] is True
        assert body["url"]

    def test_a_folder_share_is_200_with_a_kind_not_a_404(self, client, monkeypatch):
        """A folder share is a normal outcome, not a server error."""
        import app.lib.utils.media_resolve as mr

        monkeypatch.setattr(mr, "httpx", self._fake_httpx("application/json"))

        res = client.get(
            "/api/videos/resolve",
            params={"url": "https://my.pcloud.com/publink/show?code=XZ"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["kind"] == "refused"
        assert body["playable"] is False
        assert "not a video" in body["reason"]

    def test_a_private_address_is_refused_with_a_reason(self, client):
        body = client.get(
            "/api/videos/resolve", params={"url": "http://127.0.0.1/v.mp4"}
        ).json()

        assert body["playable"] is False
        assert body["kind"] == "refused"
        assert body["reason"]