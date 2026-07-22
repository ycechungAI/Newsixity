"use client";

import { useState } from "react";
import {
  extractVideoInfo,
  type PlaylistItem,
  type PlaylistPagination,
} from "@/lib/utils/video";

interface VideoEmbedProps {
  url: string;
  title?: string;
  className?: string;
  playlistItems?: PlaylistItem[];
  playlistPagination?: PlaylistPagination;
}

export default function VideoEmbed({ url, title, playlistItems }: VideoEmbedProps) {
  const videoInfo = extractVideoInfo(url);
  const [currentEmbedUrl, setCurrentEmbedUrl] = useState(videoInfo?.embedUrl ?? "");
  const [currentTitle, setCurrentTitle] = useState(title ?? "");
  const [activeVideoId, setActiveVideoId] = useState(videoInfo?.videoId ?? "");

  if (!videoInfo) return null;

  const isAnimex = videoInfo.type === "animex";
  const isDirect = videoInfo.type === "direct";

  return (
    <div>
      {/* 16:9 embed container */}
      <div className="card-video">
        {isAnimex ? (
          <a href={url} target="_blank" rel="noopener noreferrer"
            style={{ display: "flex", alignItems: "center", justifyContent: "center", background: "#1a0a2e", color: "#fff", fontSize: 12, textDecoration: "none" }}
          >
            ▶ Watch on Animex.one
          </a>
        ) : isDirect ? (
          <video
            src={currentEmbedUrl}
            title={currentTitle}
            controls
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
        ) : (
          <iframe
            src={currentEmbedUrl}
            title={currentTitle}
            allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            loading="lazy"
          />
        )}
      </div>

      {/* Playlist (article detail page only) */}
      {playlistItems && playlistItems.length > 0 && (
        <div className="vid-playlist">
          <div className="vid-playlist-title">Playlist ({playlistItems.length} videos)</div>
          <ol>
            {playlistItems.map((item, i) => (
              <li key={item.videoId}>
                <span className="vid-playlist-num">{i + 1}.</span>
                <button
                  className={`vid-playlist-btn${activeVideoId === item.videoId ? " active" : ""}`}
                  onClick={() => {
                    setCurrentEmbedUrl(`https://www.youtube.com/embed/${item.videoId}`);
                    setCurrentTitle(item.title);
                    setActiveVideoId(item.videoId);
                  }}
                >
                  {item.title}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
