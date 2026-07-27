"use client";

import { useState, useEffect } from "react";
import { getWatchlist, addToWatchlist, removeFromWatchlist } from "@/lib/finance/api";
import type { WatchlistItemWithQuote, StockSearchResult } from "@/lib/finance/types";
import StockCard from "./StockCard";
import StockSearch from "./StockSearch";
import StockChart from "./StockChart";
import MarketIndices from "./MarketIndices";
import MarketHeatmap from "./MarketHeatmap";
import { DEFAULT_STOCKS } from "@/lib/finance/constants";
import { confirmDialog, notify } from "@/lib/ui/dialog";

export default function FinanceDashboard() {
  const [watchlist, setWatchlist] = useState<WatchlistItemWithQuote[]>([]);
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<'SP500' | 'NASDAQ' | 'DOW' | null>('SP500');

  useEffect(() => { loadWatchlist(); }, []);

  async function loadWatchlist() {
    try {
      let data = await getWatchlist();
      if (data.length === 0) {
        await Promise.allSettled(
          DEFAULT_STOCKS.map(s => addToWatchlist(s.symbol, s.name, s.exchange))
        );
        data = await getWatchlist();
      }
      setWatchlist(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist");
    } finally {
      setInitialLoading(false);
    }
  }

  async function handleAddStock(stock: StockSearchResult) {
    const newItem: WatchlistItemWithQuote = {
      id: 0,
      symbol: stock.symbol,
      name: stock.name,
      exchange: stock.exchange,
      addedAt: new Date().toISOString(),
      quote: null,
      loading: true,
      error: null,
    };
    setWatchlist(prev => [newItem, ...prev]);
    try {
      await addToWatchlist(stock.symbol, stock.name, stock.exchange);
      await loadWatchlist();
    } catch (e) {
      void notify(e instanceof Error ? e.message : "Failed to add stock");
      setWatchlist(prev => prev.filter(item => item.symbol !== stock.symbol));
    }
  }

  async function handleRemoveStock(id: number) {
    if (!await confirmDialog("Remove this stock from your watchlist?")) return;
    try {
      await removeFromWatchlist(id);
      setWatchlist(prev => prev.filter(item => item.id !== id));
    } catch {
      void notify("Failed to remove stock");
    }
  }

  async function handleRefresh() {
    setInitialLoading(true);
    await loadWatchlist();
  }

  if (initialLoading) {
    return (
      <div className="fin-page">
        <div className="fin-grid">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="fin-card" style={{ minHeight: 90, opacity: 0.3 }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fin-page">
        <div style={{ fontSize: 11, color: "#ef4444", marginBottom: 8 }}>{error}</div>
        <button className="tb-btn" onClick={handleRefresh}>Retry</button>
      </div>
    );
  }

  const heatmapTitle =
    selectedIndex === 'DOW' ? 'DOW 30' :
    selectedIndex === 'NASDAQ' ? 'NASDAQ-100' : 'S&P 500';

  return (
    <div className="fin-page">
      {/* Header */}
      <div className="fin-header">
        <div>
          <div className="page-title">Finance</div>
          <div className="page-sub">Market overview &amp; watchlist</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button className="tb-btn" onClick={handleRefresh} title="Refresh quotes">↺ Refresh</button>
          <StockSearch onStockSelect={handleAddStock} />
        </div>
      </div>

      {/* Indices */}
      <MarketIndices onIndexClick={setSelectedIndex} selectedIndex={selectedIndex} />

      {/* Heatmap */}
      <div className="fin-section-head" style={{ marginBottom: 4 }}>
        <span className="fin-section-title">{heatmapTitle} Heatmap</span>
        {selectedIndex && (
          <button className="tb-btn" onClick={() => setSelectedIndex(null)}>Show All</button>
        )}
      </div>
      <MarketHeatmap indexFilter={selectedIndex} />

      {/* Watchlist */}
      <div className="fin-section-head" style={{ marginTop: 14 }}>
        <span className="fin-section-title">My Watchlist</span>
        <span className="fin-section-count">{watchlist.length} stock{watchlist.length !== 1 ? "s" : ""}</span>
      </div>

      {watchlist.length > 0 ? (
        <div className="fin-grid">
          {watchlist.map(item => (
            <StockCard
              key={item.id}
              item={item}
              onRemove={handleRemoveStock}
              onClick={setSelectedStock}
            />
          ))}
        </div>
      ) : (
        <div className="empty">
          <div className="empty-title">No stocks in watchlist</div>
          <div className="empty-desc">Search for stocks above to add them.</div>
        </div>
      )}

      {/* Chart modal */}
      {selectedStock && (
        <div className="fin-modal-overlay" onClick={() => setSelectedStock(null)}>
          <div className="fin-modal" onClick={e => e.stopPropagation()}>
            <div className="fin-modal-head">
              <span className="fin-modal-title">{selectedStock}</span>
              <button className="fin-modal-close" onClick={() => setSelectedStock(null)}>✕ Close</button>
            </div>
            <div className="fin-modal-body">
              <StockChart symbol={selectedStock} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
