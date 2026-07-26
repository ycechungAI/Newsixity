import type { Podcast } from "@/types";

interface Props {
  podcasts: Podcast[];
  selectedId?: number;
  onSelect: (podcast: Podcast) => void;
  onUnsubscribe: (id: number) => void;
  onToggleFavorite: (id: number, currentFavorite: boolean) => void;
}

export default function PodcastsList({
  podcasts,
  selectedId,
  onSelect,
  onUnsubscribe,
  onToggleFavorite,
}: Props) {
  if (podcasts.length === 0) {
    return (
      <div className="empty">
        <div className="empty-title">No podcasts subscribed</div>
        <div className="empty-desc">Add a feed URL above to get started.</div>
      </div>
    );
  }

  return (
    <div className="podcast-list">
      {podcasts.map((podcast) => (
        <div
          key={podcast.id}
          className={`podcast-item${selectedId === podcast.id ? " selected" : ""}`}
          onClick={() => onSelect(podcast)}
        >
          {podcast.imageUrl && (
            <img className="podcast-item-img" src={podcast.imageUrl} alt="" />
          )}
          <div className="podcast-item-body">
            <div className="podcast-item-title">{podcast.title}</div>
            {podcast.author && <div className="podcast-item-author">{podcast.author}</div>}
          </div>
          <div className="podcast-item-actions">
            <button
              className={`act-btn${podcast.isFavorite ? " is-saved" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleFavorite(podcast.id, podcast.isFavorite);
              }}
              title={podcast.isFavorite ? "Unfavorite" : "Favorite"}
              aria-label={podcast.isFavorite ? "Unfavorite" : "Favorite"}
            >
              {podcast.isFavorite ? "★" : "☆"}
            </button>
            <button
              className="act-btn"
              onClick={(e) => {
                e.stopPropagation();
                onUnsubscribe(podcast.id);
              }}
              title="Unsubscribe"
              aria-label="Unsubscribe"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
