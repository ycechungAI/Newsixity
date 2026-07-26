import { useCallback, useEffect, useRef, useState } from "react";
import type { Podcast, PodcastEpisode } from "@/types";

const PROGRESS_WRITE_INTERVAL_MS = 10_000;
const PLAYBACK_RATES = [1, 1.25, 1.5, 2];
const RESUME_END_BUFFER_SECONDS = 3;

interface Props {
  podcast: Podcast;
  onClose: () => void;
}

function formatTime(totalSeconds: number): string {
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return "0:00";
  const s = Math.floor(totalSeconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const ss = String(sec).padStart(2, "0");
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${ss}`;
  return `${m}:${ss}`;
}

async function updateEpisode(
  episodeId: number,
  updates: { progress_seconds?: number; is_favorite?: boolean; is_played?: boolean }
): Promise<void> {
  try {
    await fetch(`/api/podcasts/episodes/${episodeId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
  } catch {
    // Best-effort; progress writes are not critical enough to surface an error.
  }
}

export default function PodcastPlayer({ podcast, onClose }: Props) {
  const [episodes, setEpisodes] = useState<PodcastEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEpisode, setSelectedEpisode] = useState<PodcastEpisode | null>(null);

  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);

  const fetchEpisodes = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/podcasts/${podcast.id}/episodes?limit=100`);
      if (!response.ok) throw new Error("Failed to fetch episodes");
      const data = await response.json();
      setEpisodes(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [podcast.id]);

  useEffect(() => {
    fetchEpisodes();
  }, [fetchEpisodes]);

  // Apply the speed control without reloading the current episode.
  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = playbackRate;
  }, [playbackRate]);

  // Load the selected episode into the <audio> element, attach playback
  // listeners for this episode only, and flush progress + detach on
  // episode change or unmount so listeners never double up.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !selectedEpisode) return;

    const episodeId = selectedEpisode.id;
    let lastWriteAt = 0;

    audio.pause();
    audio.src = selectedEpisode.audioUrl;
    audio.playbackRate = playbackRate;
    audio.load();
    setIsPlaying(false);
    setCurrentTime(selectedEpisode.progressSeconds || 0);
    setDuration(selectedEpisode.durationSeconds || 0);

    const handleLoadedMetadata = () => {
      const total = audio.duration || selectedEpisode.durationSeconds || 0;
      setDuration(total);
      const resumeAt = selectedEpisode.progressSeconds;
      if (resumeAt > 0 && resumeAt < total - RESUME_END_BUFFER_SECONDS) {
        audio.currentTime = resumeAt;
        setCurrentTime(resumeAt);
      }
    };

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
      const now = Date.now();
      if (now - lastWriteAt >= PROGRESS_WRITE_INTERVAL_MS) {
        lastWriteAt = now;
        updateEpisode(episodeId, { progress_seconds: Math.floor(audio.currentTime) });
      }
    };

    const handlePlay = () => setIsPlaying(true);

    const handlePause = () => {
      setIsPlaying(false);
      lastWriteAt = Date.now();
      updateEpisode(episodeId, { progress_seconds: Math.floor(audio.currentTime) });
    };

    const handleEnded = () => {
      setIsPlaying(false);
      lastWriteAt = Date.now();
      updateEpisode(episodeId, {
        progress_seconds: Math.floor(audio.duration || 0),
        is_played: true,
      });
      setEpisodes((prev) =>
        prev.map((e) => (e.id === episodeId ? { ...e, isPlayed: true } : e))
      );
    };

    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("play", handlePlay);
    audio.addEventListener("pause", handlePause);
    audio.addEventListener("ended", handleEnded);

    return () => {
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("play", handlePlay);
      audio.removeEventListener("pause", handlePause);
      audio.removeEventListener("ended", handleEnded);
      if (audio.currentTime > 0) {
        updateEpisode(episodeId, { progress_seconds: Math.floor(audio.currentTime) });
      }
      audio.pause();
    };
    // playbackRate intentionally excluded — applied by the separate effect
    // above so changing speed mid-playback doesn't reload the episode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEpisode]);

  const togglePlayPause = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) audio.play();
    else audio.pause();
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio) return;
    const value = Number(e.target.value);
    audio.currentTime = value;
    setCurrentTime(value);
  };

  const handleToggleFavorite = async (episode: PodcastEpisode) => {
    const nextFavorite = !episode.isFavorite;
    try {
      const response = await fetch(`/api/podcasts/episodes/${episode.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_favorite: nextFavorite }),
      });
      if (!response.ok) throw new Error("Failed to update favorite");
      setEpisodes((prev) =>
        prev.map((e) => (e.id === episode.id ? { ...e, isFavorite: nextFavorite } : e))
      );
      if (selectedEpisode?.id === episode.id) {
        setSelectedEpisode({ ...selectedEpisode, isFavorite: nextFavorite });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update favorite");
    }
  };

  if (loading) {
    return <div className="empty">Loading episodes…</div>;
  }

  return (
    <div className="podcast-player">
      <div className="podcast-player-head">
        <div>
          <div className="podcast-player-title">{podcast.title}</div>
          {podcast.author && <div className="podcast-player-author">{podcast.author}</div>}
        </div>
        <button className="act-btn" onClick={onClose} aria-label="Close player">
          ✕ Close
        </button>
      </div>

      {error && <div className="settings-msg err">{error}</div>}

      <audio ref={audioRef} preload="metadata" />

      {selectedEpisode && (
        <div className="podcast-now-playing">
          <div className="podcast-now-playing-title">{selectedEpisode.title}</div>
          <div className="podcast-controls">
            <button
              className="podcast-play-btn"
              onClick={togglePlayPause}
              aria-label={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? "❚❚" : "▶"}
            </button>
            <span className="podcast-time">{formatTime(currentTime)}</span>
            <input
              className="podcast-seek"
              type="range"
              min={0}
              max={duration || 0}
              step={1}
              value={Math.min(currentTime, duration || 0)}
              onChange={handleSeek}
              aria-label="Seek"
            />
            <span className="podcast-time">{formatTime(duration)}</span>
            <select
              className="podcast-speed-select"
              value={playbackRate}
              onChange={(e) => setPlaybackRate(Number(e.target.value))}
              aria-label="Playback speed"
            >
              {PLAYBACK_RATES.map((rate) => (
                <option key={rate} value={rate}>
                  {rate}×
                </option>
              ))}
            </select>
            <button
              className={`act-btn${selectedEpisode.isFavorite ? " is-saved" : ""}`}
              onClick={() => handleToggleFavorite(selectedEpisode)}
              aria-label={selectedEpisode.isFavorite ? "Unfavorite episode" : "Favorite episode"}
            >
              {selectedEpisode.isFavorite ? "★" : "☆"}
            </button>
          </div>
        </div>
      )}

      {episodes.length === 0 ? (
        <div className="empty">
          <div className="empty-title">No episodes yet</div>
        </div>
      ) : (
        <div className="podcast-episode-list">
          {episodes.map((episode) => (
            <div
              key={episode.id}
              className={`podcast-episode-item${selectedEpisode?.id === episode.id ? " selected" : ""}${episode.isPlayed ? " played" : ""}`}
              onClick={() => setSelectedEpisode(episode)}
            >
              <span className="podcast-episode-title">{episode.title}</span>
              {episode.durationSeconds != null && (
                <span className="podcast-episode-meta">
                  {formatTime(episode.durationSeconds)}
                </span>
              )}
              {episode.isFavorite && <span className="podcast-episode-meta">★</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
