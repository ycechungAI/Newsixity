"use client";

import { useState, useEffect, useCallback } from "react";
import { getHeatmapSnapshot, getHeatmapDates } from "@/lib/finance/api";
import { SECTOR_COLORS, DOW_30_SYMBOLS, NASDAQ_SYMBOLS } from "@/lib/finance/sp500";
import type { HeatmapStock } from "@/lib/finance/types";

interface MarketHeatmapProps {
  indexFilter?: 'SP500' | 'NASDAQ' | 'DOW' | null;
}

export default function MarketHeatmap({ indexFilter }: MarketHeatmapProps) {
  const [stocks, setStocks] = useState<HeatmapStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [showDatePicker, setShowDatePicker] = useState(false);

  const loadHeatmapData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getHeatmapSnapshot(selectedDate || undefined);
      setStocks(data.stocks);
    } catch (e) {
      console.error("[Newsixity] Failed to load heatmap:", e);
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  const loadAvailableDates = useCallback(async () => {
    try {
      setAvailableDates(await getHeatmapDates());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    void loadHeatmapData();
    void loadAvailableDates();
  }, [loadHeatmapData, loadAvailableDates]);

  if (loading) {
    return <div className="fin-hmap-grid" style={{ minHeight: 200, opacity: 0.4 }} />;
  }

  const filteredStocks = stocks.filter(s => {
    if (!indexFilter) return true;
    if (indexFilter === 'DOW') return DOW_30_SYMBOLS.includes(s.symbol);
    if (indexFilter === 'NASDAQ') return NASDAQ_SYMBOLS.includes(s.symbol);
    return true;
  });

  const stocksBySector = filteredStocks.reduce((acc, s) => {
    if (!acc[s.sector]) acc[s.sector] = [];
    acc[s.sector].push(s);
    return acc;
  }, {} as Record<string, HeatmapStock[]>);

  const sectors = Object.keys(stocksBySector).sort((a, b) => {
    const sum = (arr: HeatmapStock[]) => arr.reduce((n, s) => n + (s.marketCap || 0), 0);
    return sum(stocksBySector[b]) - sum(stocksBySector[a]);
  });

  const displayStocks = selectedSector ? (stocksBySector[selectedSector] || []) : filteredStocks;

  const currentDate = selectedDate || new Date().toISOString().split('T')[0];
  const formattedDate = new Date(currentDate + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  });

  return (
    <div className="fin-hmap-wrap">
      {/* Controls */}
      <div className="fin-hmap-controls">
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <button className="fin-hmap-date-btn" onClick={() => setShowDatePicker(!showDatePicker)}>
            📅 {formattedDate}
          </button>
          {selectedDate && (
            <button className="fin-hmap-date-btn" onClick={() => setSelectedDate('')}>Today</button>
          )}
        </div>
        <button className="fin-hmap-date-btn" onClick={loadHeatmapData} title="Refresh">↺</button>
      </div>

      {showDatePicker && availableDates.length > 0 && (
        <div className="fin-date-picker">
          <div className="fin-date-picker-title">Historical snapshots:</div>
          <div className="fin-date-list">
            {availableDates.map((date) => (
              <button
                key={date}
                className={`fin-date-item${selectedDate === date ? " active" : ""}`}
                onClick={() => { setSelectedDate(date); setShowDatePicker(false); }}
              >
                {new Date(date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Sector filter */}
      <div className="fin-sector-bar">
        <button
          className={`fin-sector-btn${!selectedSector ? " active" : ""}`}
          onClick={() => setSelectedSector(null)}
        >All</button>
        {sectors.map((sector) => (
          <button
            key={sector}
            className={`fin-sector-btn${selectedSector === sector ? " active" : ""}`}
            onClick={() => setSelectedSector(sector)}
            style={{ borderLeftColor: SECTOR_COLORS[sector] || "var(--border)", borderLeftWidth: 3 }}
          >
            {sector} ({stocksBySector[sector].length})
          </button>
        ))}
      </div>

      {/* Grid */}
      {displayStocks.length > 0 ? (
        <div className="fin-hmap-grid">
          {displayStocks
            .sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))
            .map((stock) => {
              const isPositive = stock.changePercent >= 0;
              const intensity = Math.min(Math.abs(stock.changePercent) / 5, 1);
              const maxCap = Math.max(...displayStocks.map(s => s.marketCap || 0));
              const size = 50 + 110 * ((stock.marketCap || 0) / maxCap);
              const bg = isPositive
                ? `rgba(34,197,94,${0.2 + intensity * 0.8})`
                : `rgba(239,68,68,${0.2 + intensity * 0.8})`;

              return (
                <div
                  key={stock.symbol}
                  className="fin-hmap-tile"
                  style={{ width: size, height: size * 0.7, backgroundColor: bg }}
                >
                  <span className="fin-hmap-sym">{stock.symbol}</span>
                  <span className={`fin-hmap-pct ${isPositive ? "pos" : "neg"}`}>
                    {isPositive ? "+" : ""}{stock.changePercent.toFixed(1)}%
                  </span>
                  <div className="fin-hmap-tooltip">
                    <div style={{ fontWeight: 700 }}>{stock.name}</div>
                    <div>${stock.price.toFixed(2)} · {isPositive ? "+" : ""}{stock.changePercent.toFixed(2)}%</div>
                    <div style={{ color: "#aaa" }}>Cap ${((stock.marketCap || 0) / 1e9).toFixed(1)}B</div>
                  </div>
                </div>
              );
            })}
        </div>
      ) : (
        <div className="empty"><div className="empty-title">No heatmap data for this date</div></div>
      )}

      <div className="fin-hmap-legend">
        <span><span className="fin-legend-swatch" style={{ background: "rgba(34,197,94,.8)" }} />Positive</span>
        <span><span className="fin-legend-swatch" style={{ background: "rgba(239,68,68,.8)" }} />Negative</span>
        <span>Size = Market Cap</span>
        <span>Intensity = % Change</span>
      </div>
    </div>
  );
}
