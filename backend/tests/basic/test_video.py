"""Tests for video utility functions."""

import json

import pytest
from app.lib.utils.video import (
    PLAYLIST_ID_RE,
    PlaylistItem,
    _collect_lockups,
    _extract_initial_data,
    extract_video_info,
    fetch_youtube_playlist,
    is_video_url,
)


class TestExtractVideoInfoYouTubeStandard:
    """Tests for extract_video_info with YouTube standard URLs."""

    def test_extracts_video_id_from_youtube_com_watch_url(self):
        info = extract_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert info is not None
        assert info.type == "youtube"
        assert info.video_id == "dQw4w9WgXcQ"
        assert info.embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    def test_works_with_m_youtube_com(self):
        info = extract_video_info("https://m.youtube.com/watch?v=abc123")
        assert info is not None
        assert info.type == "youtube"
        assert info.video_id == "abc123"

    def test_works_with_music_youtube_com(self):
        info = extract_video_info("https://music.youtube.com/watch?v=abc123")
        assert info is not None
        assert info.type == "youtube"
        assert info.video_id == "abc123"

    def test_attaches_playlist_id_when_list_param_is_present(self):
        info = extract_video_info(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx123"
        )
        assert info is not None
        assert info.playlist_id == "PLxxx123"
        assert info.playlist_embed_url is not None
        assert "PLxxx123" in info.playlist_embed_url

    def test_returns_none_when_youtube_com_url_has_no_v_param(self):
        info = extract_video_info("https://www.youtube.com/channel/UCxxx")
        assert info is None


class TestExtractVideoInfoYouTubeShortLink:
    """Tests for extract_video_info with youtu.be short links."""

    def test_extracts_video_id_from_youtu_be_url(self):
        info = extract_video_info("https://youtu.be/dQw4w9WgXcQ")
        assert info is not None
        assert info.type == "youtube"
        assert info.video_id == "dQw4w9WgXcQ"
        assert info.embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    def test_attaches_playlist_when_list_param_present_on_youtu_be(self):
        info = extract_video_info("https://youtu.be/abc123?list=PLyyy")
        assert info is not None
        assert info.playlist_id == "PLyyy"


class TestExtractVideoInfoYouTubeShorts:
    """Tests for extract_video_info with YouTube Shorts."""

    def test_extracts_video_id_from_shorts_url(self):
        info = extract_video_info("https://www.youtube.com/shorts/abc123XYZ")
        assert info is not None
        assert info.type == "youtube"
        assert info.video_id == "abc123XYZ"
        assert info.embed_url == "https://www.youtube.com/embed/abc123XYZ"


class TestExtractVideoInfoPlaylistOnly:
    """Tests for extract_video_info with playlist-only URLs."""

    def test_handles_playlist_only_urls(self):
        info = extract_video_info(
            "https://www.youtube.com/playlist?list=PLxxx123"
        )
        assert info is not None
        assert info.type == "youtube"
        assert info.video_id == ""
        assert "PLxxx123" in info.embed_url


class TestExtractVideoInfoVimeo:
    """Tests for extract_video_info with Vimeo URLs."""

    def test_extracts_numeric_video_id_from_vimeo_com(self):
        info = extract_video_info("https://vimeo.com/123456789")
        assert info is not None
        assert info.type == "vimeo"
        assert info.video_id == "123456789"
        assert info.embed_url == "https://player.vimeo.com/video/123456789"

    def test_works_with_www_vimeo_com(self):
        info = extract_video_info("https://www.vimeo.com/987654321")
        assert info is not None
        assert info.type == "vimeo"

    def test_returns_none_for_non_numeric_vimeo_path(self):
        info = extract_video_info("https://vimeo.com/channels/my-channel")
        assert info is None


class TestExtractVideoInfoDailymotion:
    """Tests for extract_video_info with Dailymotion URLs."""

    def test_extracts_video_id_from_dailymotion_com_url(self):
        info = extract_video_info("https://www.dailymotion.com/video/x7tgad2")
        assert info is not None
        assert info.type == "dailymotion"
        assert info.video_id == "x7tgad2"
        assert "x7tgad2" in info.embed_url

    def test_extracts_video_id_from_dai_ly_short_link(self):
        info = extract_video_info("https://dai.ly/x7tgad2")
        assert info is not None
        assert info.type == "dailymotion"
        assert info.video_id == "x7tgad2"


class TestExtractVideoInfoOdysee:
    """Tests for extract_video_info with Odysee URLs."""

    def test_extracts_path_from_odysee_com_url(self):
        info = extract_video_info(
            "https://odysee.com/@SomeChannel:1/some-video:2"
        )
        assert info is not None
        assert info.type == "odysee"
        assert "odysee.com/$/embed" in info.embed_url

    def test_returns_none_for_odysee_dollar_utility_paths(self):
        info = extract_video_info("https://odysee.com/$/settings")
        assert info is None


class TestExtractVideoInfoInvalid:
    """Tests for extract_video_info with invalid/non-video URLs."""

    def test_returns_none_for_regular_web_page(self):
        assert extract_video_info("https://example.com/article") is None

    def test_returns_none_for_invalid_url(self):
        assert extract_video_info("not-a-url") is None

    def test_returns_none_for_empty_string(self):
        assert extract_video_info("") is None


class TestIsVideoUrl:
    """Tests for is_video_url function."""

    def test_returns_true_for_youtube_url(self):
        assert (
            is_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            is True
        )

    def test_returns_true_for_vimeo_url(self):
        assert is_video_url("https://vimeo.com/123456789") is True

    def test_returns_false_for_non_video_url(self):
        assert is_video_url("https://example.com/news") is False

    def test_returns_false_for_invalid_url(self):
        assert is_video_url("definitely not a url") is False


def _lockup(video_id: str, title: str) -> dict:
    """Minimal ytInitialData-shaped node for one playlist entry."""
    return {
        "lockupViewModel": {
            "contentId": video_id,
            "metadata": {
                "lockupMetadataViewModel": {"title": {"content": title}}
            },
        }
    }


class TestPlaylistIdValidation:
    """The id is interpolated into a URL, so it must be strictly validated."""

    @pytest.mark.parametrize(
        "playlist_id",
        ["PLabc123", "UU_x5XG1OV2P6uZZ5FSM9Ttw", "a-b_c", "AB"],
    )
    def test_accepts_real_playlist_ids(self, playlist_id):
        assert PLAYLIST_ID_RE.match(playlist_id)

    @pytest.mark.parametrize(
        "playlist_id",
        [
            "",
            "A",  # too short
            "../../etc/passwd",
            "abc&list=other",  # query-param injection
            "abc?foo=bar",
            "abc/def",
            "abc def",
            "a" * 65,  # too long
        ],
    )
    def test_rejects_unsafe_ids(self, playlist_id):
        assert not PLAYLIST_ID_RE.match(playlist_id)

    def test_fetch_short_circuits_on_bad_id_without_network(self):
        # No network guard needed: an invalid id must never reach httpx.
        assert fetch_youtube_playlist("../../etc/passwd") == {
            "items": [],
            "totalItems": 0,
            "source": "none",
        }


class TestCollectLockups:
    """Parsing of YouTube's ytInitialData / InnerTube payloads."""

    def test_extracts_videos_in_document_order(self):
        tree = {"contents": [_lockup("aaa", "First"), _lockup("bbb", "Second")]}
        items: list[PlaylistItem] = []
        _collect_lockups(tree, items, set())
        assert [(i.video_id, i.title) for i in items] == [
            ("aaa", "First"),
            ("bbb", "Second"),
        ]
        assert items[0].url == "https://www.youtube.com/watch?v=aaa"

    def test_deduplicates_across_continuation_rounds(self):
        items: list[PlaylistItem] = []
        seen: set[str] = set()
        _collect_lockups({"c": [_lockup("aaa", "First")]}, items, seen)
        # Same video reappearing in a later round must not be added twice.
        _collect_lockups(
            {"c": [_lockup("aaa", "First"), _lockup("bbb", "Second")]}, items, seen
        )
        assert [i.video_id for i in items] == ["aaa", "bbb"]

    def test_returns_continuation_token(self):
        tree = {
            "contents": [_lockup("aaa", "First")],
            "continuations": {"continuationCommand": {"token": "TOKEN123"}},
        }
        assert _collect_lockups(tree, [], set()) == "TOKEN123"

    def test_returns_none_when_no_continuation(self):
        assert _collect_lockups({"contents": [_lockup("aaa", "x")]}, [], set()) is None

    def test_falls_back_to_placeholder_title(self):
        items: list[PlaylistItem] = []
        _collect_lockups({"lockupViewModel": {"contentId": "aaa"}}, items, set())
        assert items[0].title == "Untitled"

    def test_yields_nothing_for_the_old_renderer_key(self):
        """Regression guard for the rename that silently broke scraping.

        YouTube renamed playlistVideoRenderer -> lockupViewModel. Callers
        rely on an empty result meaning "shape changed, fall back to RSS",
        so the old key must not be quietly accepted.
        """
        tree = {"contents": [{"playlistVideoRenderer": {"videoId": "aaa"}}]}
        items: list[PlaylistItem] = []
        assert _collect_lockups(tree, items, set()) is None
        assert items == []

    def test_survives_deeply_nested_payloads(self):
        """The walk is iterative; deep nesting must not hit the recursion limit."""
        tree: dict = _lockup("deep", "Deep")
        for _ in range(3000):
            tree = {"nested": tree}
        items: list[PlaylistItem] = []
        _collect_lockups(tree, items, set())
        assert [i.video_id for i in items] == ["deep"]


class TestExtractInitialData:
    def test_extracts_embedded_json(self):
        payload = {"contents": [_lockup("aaa", "First")]}
        html = f"<html><script>var ytInitialData = {json.dumps(payload)};</script></html>"
        assert _extract_initial_data(html) == payload

    def test_returns_none_when_absent(self):
        assert _extract_initial_data("<html>no data here</html>") is None

    def test_returns_none_on_malformed_json(self):
        assert _extract_initial_data("var ytInitialData = {broken;</script>") is None
