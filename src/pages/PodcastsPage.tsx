import { useCallback, useEffect, useState } from "react";
import type { Podcast } from "@/types";
import PodcastsList from "@/components/podcasts/PodcastsList";
import PodcastPlayer from "@/components/podcasts/PodcastPlayer";

export default function PodcastsPage() {
  const [podcasts, setPodcasts] = useState<Podcast[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedUrl, setFeedUrl] = useState("");
  const [subscribing, setSubscribing] = useState(false);
  const [selectedPodcast, setSelectedPodcast] = useState<Podcast | null>(null);

  const fetchPodcasts = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/podcasts");
      if (!response.ok) throw new Error("Failed to fetch podcasts");
      const data = await response.json();
      setPodcasts(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPodcasts();
  }, [fetchPodcasts]);

  const handleSubscribe = async () => {
    if (!feedUrl.trim()) {
      setError("Please enter a feed URL");
      return;
    }

    try {
      setSubscribing(true);
      const response = await fetch("/api/podcasts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feed_url: feedUrl.trim() }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || "Failed to subscribe");
      }
      const newPodcast = await response.json();
      setPodcasts((prev) =>
        prev.some((p) => p.id === newPodcast.id) ? prev : [...prev, newPodcast]
      );
      setFeedUrl("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to subscribe");
    } finally {
      setSubscribing(false);
    }
  };

  const handleUnsubscribe = async (id: number) => {
    try {
      const response = await fetch(`/api/podcasts/${id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Failed to unsubscribe");
      setPodcasts((prev) => prev.filter((p) => p.id !== id));
      if (selectedPodcast?.id === id) setSelectedPodcast(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unsubscribe");
    }
  };

  const handleToggleFavorite = async (id: number, currentFavorite: boolean) => {
    try {
      const response = await fetch(`/api/podcasts/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_favorite: !currentFavorite }),
      });
      if (!response.ok) throw new Error("Failed to update favorite");
      setPodcasts((prev) =>
        prev.map((p) => (p.id === id ? { ...p, isFavorite: !currentFavorite } : p))
      );
      if (selectedPodcast?.id === id) {
        setSelectedPodcast({ ...selectedPodcast, isFavorite: !currentFavorite });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update favorite");
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">Podcasts</div>
          <div className="page-sub">
            {podcasts.length} subscription{podcasts.length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

      <div className="settings-row">
        <input
          className="settings-input"
          value={feedUrl}
          onChange={(e) => setFeedUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubscribe();
          }}
          placeholder="Podcast RSS feed URL"
          disabled={subscribing}
        />
        <button
          className="settings-save-btn"
          onClick={handleSubscribe}
          disabled={subscribing || !feedUrl.trim()}
        >
          {subscribing ? "Subscribing…" : "Subscribe"}
        </button>
      </div>

      {error && <div className="settings-msg err">{error}</div>}

      {loading ? (
        <div className="empty">Loading podcasts…</div>
      ) : (
        <div className="podcast-layout">
          <PodcastsList
            podcasts={podcasts}
            selectedId={selectedPodcast?.id}
            onSelect={setSelectedPodcast}
            onUnsubscribe={handleUnsubscribe}
            onToggleFavorite={handleToggleFavorite}
          />

          {selectedPodcast && (
            <PodcastPlayer podcast={selectedPodcast} onClose={() => setSelectedPodcast(null)} />
          )}
        </div>
      )}
    </div>
  );
}
