"use client";

import { extractVideoInfo } from "@/lib/utils/video";

interface VideoEmbedProps {
  url: string;
  title?: string;
  className?: string;
}

export default function VideoEmbed({ url, title, className = "" }: VideoEmbedProps) {
  const videoInfo = extractVideoInfo(url);

  if (!videoInfo) {
    return null;
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="relative w-full overflow-hidden rounded-lg bg-black">
        {/* 16:9 aspect ratio */}
        <div style={{ paddingBottom: "56.25%" }} className="relative">
          <iframe
            src={videoInfo.embedUrl}
            title={title}
            className="absolute top-0 left-0 w-full h-full border-0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            loading="lazy"
          />
        </div>
      </div>

      {/* YouTube playlist below the video */}
      {videoInfo.playlistEmbedUrl && videoInfo.playlistEmbedUrl !== videoInfo.embedUrl && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Playlist</h4>
          <div className="relative w-full overflow-hidden rounded-lg bg-black">
            <div style={{ paddingBottom: "56.25%" }} className="relative">
              <iframe
                src={videoInfo.playlistEmbedUrl}
                title={title ? `${title} - Playlist` : "Playlist"}
                className="absolute top-0 left-0 w-full h-full border-0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                loading="lazy"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
