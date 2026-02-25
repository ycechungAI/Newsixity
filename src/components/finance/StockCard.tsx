"use client";

import type { WatchlistItemWithQuote } from "@/lib/finance/types";

interface StockCardProps {
  item: WatchlistItemWithQuote;
  onRemove?: (id: number) => void;
  onClick?: (symbol: string) => void;
}

export default function StockCard({ item, onRemove, onClick }: StockCardProps) {
  const { quote, loading, error } = item;
  const isPositive = quote ? quote.change >= 0 : false;

  if (loading) {
    return <div className="fin-card" style={{ minHeight: 80, opacity: 0.4 }} />;
  }

  if (error && !quote) {
    return (
      <div className="fin-card">
        <div className="fin-card-head">
          <span className="fin-card-sym">{item.symbol}</span>
          {onRemove && (
            <button className="fin-card-remove" onClick={() => onRemove(item.id)} title="Remove">✕</button>
          )}
        </div>
        <div style={{ fontSize: 10, color: "#ef4444" }}>{error}</div>
      </div>
    );
  }

  if (!quote) return null;

  return (
    <div className="fin-card" onClick={() => onClick?.(item.symbol)}>
      <div className="fin-card-head">
        <div>
          <span className="fin-card-sym">{quote.symbol}</span>
          <span className="fin-card-exch">{quote.exchange}</span>
        </div>
        {onRemove && (
          <button
            className="fin-card-remove"
            onClick={(e) => { e.stopPropagation(); onRemove(item.id); }}
            title="Remove"
          >✕</button>
        )}
      </div>
      <div className="fin-card-name">{item.name}</div>
      <div className="fin-card-price">${quote.price.toFixed(2)}</div>
      <div className={`fin-card-chg ${isPositive ? "pos" : "neg"}`}>
        {isPositive ? "+" : ""}{quote.change.toFixed(2)} ({isPositive ? "+" : ""}{quote.changePercent.toFixed(2)}%)
      </div>
      <div className="fin-card-meta">
        {quote.marketState && (
          <span className={quote.marketState === "REGULAR" ? "pos" : ""}>
            {quote.marketState === "REGULAR" ? "● Open" : "Closed"}
          </span>
        )}
        {quote.volume && <span>Vol {(quote.volume / 1e6).toFixed(1)}M</span>}
      </div>
    </div>
  );
}
