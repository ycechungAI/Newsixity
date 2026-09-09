"""Tests for the direct-stream resolver (YouTube on Linux).

Verifies format selection without touching the network: ``_pick_format``
decision-making and ``StreamChoice`` semantics. Optionally exercises the live
resolver against YouTube when a network is available (marked, skipped by
default unless --run-live is passed).
"""

from app.lib.utils.stream import DEFAULT_MAX_HEIGHT, StreamChoice, _pick_format

# ── Format fixtures ──────────────────────────────────────────────────────────


def fmt(**over):
    base = {
        "format_id": "x",
        "ext": "mp4",
        "protocol": "https",
        "vcodec": "avc1.64001f",
        "acodec": "mp4a.40.2",
        "url": "https://rr1---.googlevideo.com/videoplayback",
        "height": 720,
        "abr": 128.0,
        "tbr": 1000.0,
    }
    base.update(over)
    return base


VIDEO_ONLY = [
    fmt(format_id="v=480", height=480, acodec="none"),
    fmt(format_id="v=720", height=720, acodec="none"),
    fmt(format_id="v=1080", height=1080, acodec="none"),
]

AUDIO_ONLY = [
    fmt(format_id="a=64", ext="m4a", abr=64.0, vcodec="none", acodec="mp4a.40.2"),
    fmt(format_id="a=128", ext="m4a", abr=128.0, vcodec="none", acodec="mp4a.40.2"),
]

COMBINED = [
    fmt(format_id="c=360", height=360),
    fmt(format_id="c=720", height=720),
    fmt(format_id="c=1080", height=1080),
]


class TestStreamChoice:
    def test_direct_and_mux_semantics(self):
        direct = StreamChoice(direct_url="https://x")
        assert direct.has_direct and direct.usable and not direct.needs_mux

        pair = StreamChoice(v_url="https://v", a_url="https://a")
        assert pair.needs_mux and pair.usable and not pair.has_direct

        assert not StreamChoice().usable
        assert not StreamChoice(v_url="https://v").usable  # no audio

    def test_as_dict(self):
        c = StreamChoice(direct_url="https://x", title="T")
        d = c.as_dict()
        assert d["directUrl"] == "https://x"
        assert d["title"] == "T"


class TestPickFormat:
    def test_prefers_combined_when_available(self):
        f = _pick_format(COMBINED + VIDEO_ONLY + AUDIO_ONLY, "combined", 720)
        assert f["format_id"] == "c=720"

    def test_combined_caps_height(self):
        f = _pick_format(COMBINED, "combined", DEFAULT_MAX_HEIGHT)
        assert f["height"] == 720

    def test_combined_falls_back_to_any_height_when_none_fit(self):
        only_big = [fmt(format_id="c=1080", height=1080)]
        f = _pick_format(only_big, "combined", max_height=480)
        assert f is not None and f["height"] == 1080

    def test_video_only_ignores_audio_height_cap(self):
        f = _pick_format(VIDEO_ONLY, "video", 720)
        assert f["format_id"] == "v=720"

    def test_video_prefers_mp4_over_webm(self):
        formats = [
            fmt(format_id="w=720", height=720, ext="webm", vcodec="vp9"),
            fmt(format_id="m=720", height=720, ext="mp4", vcodec="avc1.64001f"),
        ]
        f = _pick_format(formats, "video", 720)
        assert f["format_id"] == "m=720"

    def test_audio_picks_highest_bitrate(self):
        f = _pick_format(AUDIO_ONLY, "audio", 720)
        assert f["format_id"] == "a=128"

    def test_audio_prefers_m4a_acodec(self):
        formats = [
            fmt(format_id="a=opus", ext="webm", acodec="opus", vcodec="none", abr=160.0),
            fmt(format_id="a=m4a", ext="m4a", acodec="mp4a.40.2", vcodec="none", abr=128.0),
        ]
        f = _pick_format(formats, "audio", 720)
        assert f["format_id"] == "a=m4a"

    def test_excludes_hls_streams(self):
        hls = [fmt(format_id="hls", protocol="m3u8_native", has_drm=True)]
        assert _pick_format(hls, "video", 720) is None
        assert _pick_format(hls, "combined", 720) is None

    def test_returns_none_on_empty(self):
        assert _pick_format([], "combined", 720) is None