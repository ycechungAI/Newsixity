import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  extractVideoInfo,
  isVideoUrl,
} from "../../src/lib/utils/video.ts";

describe("extractVideoInfo – YouTube standard", () => {
  it("extracts video ID from youtube.com watch URL", () => {
    const info = extractVideoInfo("https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    assert.ok(info);
    assert.equal(info.type, "youtube");
    assert.equal(info.videoId, "dQw4w9WgXcQ");
    assert.equal(info.embedUrl, "https://www.youtube.com/embed/dQw4w9WgXcQ");
  });

  it("works with m.youtube.com", () => {
    const info = extractVideoInfo("https://m.youtube.com/watch?v=abc123");
    assert.ok(info);
    assert.equal(info.type, "youtube");
    assert.equal(info.videoId, "abc123");
  });

  it("works with music.youtube.com", () => {
    const info = extractVideoInfo("https://music.youtube.com/watch?v=abc123");
    assert.ok(info);
    assert.equal(info.type, "youtube");
    assert.equal(info.videoId, "abc123");
  });

  it("attaches playlist ID when list param is present", () => {
    const info = extractVideoInfo(
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx123"
    );
    assert.ok(info);
    assert.equal(info.playlistId, "PLxxx123");
    assert.ok(info.playlistEmbedUrl?.includes("PLxxx123"));
  });

  it("returns null when youtube.com URL has no v param", () => {
    const info = extractVideoInfo("https://www.youtube.com/channel/UCxxx");
    assert.equal(info, null);
  });
});

describe("extractVideoInfo – YouTube short link (youtu.be)", () => {
  it("extracts video ID from youtu.be URL", () => {
    const info = extractVideoInfo("https://youtu.be/dQw4w9WgXcQ");
    assert.ok(info);
    assert.equal(info.type, "youtube");
    assert.equal(info.videoId, "dQw4w9WgXcQ");
    assert.equal(info.embedUrl, "https://www.youtube.com/embed/dQw4w9WgXcQ");
  });

  it("attaches playlist when list param present on youtu.be", () => {
    const info = extractVideoInfo("https://youtu.be/abc123?list=PLyyy");
    assert.ok(info);
    assert.equal(info.playlistId, "PLyyy");
  });
});

describe("extractVideoInfo – YouTube Shorts", () => {
  it("extracts video ID from Shorts URL", () => {
    const info = extractVideoInfo("https://www.youtube.com/shorts/abc123XYZ");
    assert.ok(info);
    assert.equal(info.type, "youtube");
    assert.equal(info.videoId, "abc123XYZ");
    assert.equal(info.embedUrl, "https://www.youtube.com/embed/abc123XYZ");
  });
});

describe("extractVideoInfo – YouTube playlist-only", () => {
  it("handles playlist-only URLs", () => {
    const info = extractVideoInfo(
      "https://www.youtube.com/playlist?list=PLxxx123"
    );
    assert.ok(info);
    assert.equal(info.type, "youtube");
    assert.equal(info.videoId, "");
    assert.ok(info.embedUrl.includes("PLxxx123"));
  });
});

describe("extractVideoInfo – Vimeo", () => {
  it("extracts numeric video ID from vimeo.com", () => {
    const info = extractVideoInfo("https://vimeo.com/123456789");
    assert.ok(info);
    assert.equal(info.type, "vimeo");
    assert.equal(info.videoId, "123456789");
    assert.equal(info.embedUrl, "https://player.vimeo.com/video/123456789");
  });

  it("works with www.vimeo.com", () => {
    const info = extractVideoInfo("https://www.vimeo.com/987654321");
    assert.ok(info);
    assert.equal(info.type, "vimeo");
  });

  it("returns null for non-numeric vimeo path", () => {
    const info = extractVideoInfo("https://vimeo.com/channels/my-channel");
    assert.equal(info, null);
  });
});

describe("extractVideoInfo – Dailymotion", () => {
  it("extracts video ID from dailymotion.com URL", () => {
    const info = extractVideoInfo("https://www.dailymotion.com/video/x7tgad2");
    assert.ok(info);
    assert.equal(info.type, "dailymotion");
    assert.equal(info.videoId, "x7tgad2");
    assert.ok(info.embedUrl.includes("x7tgad2"));
  });

  it("extracts video ID from dai.ly short link", () => {
    const info = extractVideoInfo("https://dai.ly/x7tgad2");
    assert.ok(info);
    assert.equal(info.type, "dailymotion");
    assert.equal(info.videoId, "x7tgad2");
  });
});

describe("extractVideoInfo – Odysee", () => {
  it("extracts path from odysee.com URL", () => {
    const info = extractVideoInfo(
      "https://odysee.com/@SomeChannel:1/some-video:2"
    );
    assert.ok(info);
    assert.equal(info.type, "odysee");
    assert.ok(info.embedUrl.includes("odysee.com/$/embed"));
  });

  it("returns null for Odysee $ utility paths", () => {
    const info = extractVideoInfo("https://odysee.com/$/settings");
    assert.equal(info, null);
  });
});

describe("extractVideoInfo – invalid / non-video URLs", () => {
  it("returns null for a regular web page", () => {
    assert.equal(extractVideoInfo("https://example.com/article"), null);
  });

  it("returns null for an invalid URL", () => {
    assert.equal(extractVideoInfo("not-a-url"), null);
  });

  it("returns null for an empty string", () => {
    assert.equal(extractVideoInfo(""), null);
  });
});

describe("isVideoUrl", () => {
  it("returns true for a YouTube URL", () => {
    assert.equal(
      isVideoUrl("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
      true
    );
  });

  it("returns true for a Vimeo URL", () => {
    assert.equal(isVideoUrl("https://vimeo.com/123456789"), true);
  });

  it("returns false for a non-video URL", () => {
    assert.equal(isVideoUrl("https://example.com/news"), false);
  });

  it("returns false for an invalid URL", () => {
    assert.equal(isVideoUrl("definitely not a url"), false);
  });
});
