"use client";

import { useState, useEffect } from "react";
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

  useEffect(() => {
    loadHeatmapData();
    loadAvailableDates();
  }, [selectedDate]);

  async function loadHeatmapData() {
    setLoading(true);
    try {
      const data = await getHeatmapSnapshot(selectedDate || undefined);
      setStocks(data.stocks);
    } catch (error) {
      console.error("[Newsixity] Failed to load heatmap data:", error);
    } finally {
      setLoading(false);
    }
  }

  async function loadAvailableDates() {
    try {
      const dates = await getHeatmapDates();
      setAvailableDates(dates);
    } catch (error) {
      console.error("[Newsixity] Failed to load available dates:", error);
    }
  }

  if (loading) {
    return (
      <div className="h-[500px] bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
    );
  }

  // Filter stocks by index
  const filteredStocks = stocks.filter(stock => {
    if (!indexFilter) return true; // Show all if no filter

    if (indexFilter === 'DOW') {
      return DOW_30_SYMBOLS.includes(stock.symbol);
    }

    if (indexFilter === 'NASDAQ') {
      return NASDAQ_SYMBOLS.includes(stock.symbol);
    }

    // SP500 shows all
    return true;
  });

  // Group stocks by sector
  const stocksBySector = filteredStocks.reduce((acc, stock) => {
    if (!acc[stock.sector]) {
      acc[stock.sector] = [];
    }
    acc[stock.sector].push(stock);
    return acc;
  }, {} as Record<string, HeatmapStock[]>);

  // Sort sectors by total market cap
  const sectors = Object.keys(stocksBySector).sort((a, b) => {
    const aTotal = stocksBySector[a].reduce((sum, s) => sum + (s.marketCap || 0), 0);
    const bTotal = stocksBySector[b].reduce((sum, s) => sum + (s.marketCap || 0), 0);
    return bTotal - aTotal;
  });

  const displayStocks = selectedSector
    ? stocksBySector[selectedSector] || []
    : filteredStocks;

  const indexName =
    indexFilter === 'DOW' ? 'DOW 30' :
    indexFilter === 'NASDAQ' ? 'NASDAQ-100' :
    'S&P 500';

  const currentDate = selectedDate || new Date().toISOString().split('T')[0];
  const formattedDate = new Date(currentDate + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="space-y-4">
      {/* Date picker and controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDatePicker(!showDatePicker)}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            {formattedDate}
          </button>
          {selectedDate && (
            <button
              onClick={() => setSelectedDate('')}
              className="px-3 py-2 rounded-lg text-sm font-medium bg-sky-100 dark:bg-sky-900 text-sky-700 dark:text-sky-300 hover:bg-sky-200 dark:hover:bg-sky-800 transition-colors"
            >
              Today
            </button>
          )}
        </div>
        <button
          onClick={loadHeatmapData}
          className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          title="Refresh heatmap"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* Historical dates */}
      {showDatePicker && availableDates.length > 0 && (
        <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Historical Snapshots:</p>
          <div className="flex flex-wrap gap-2">
            {availableDates.map((date) => (
              <button
                key={date}
                onClick={() => {
                  setSelectedDate(date);
                  setShowDatePicker(false);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  selectedDate === date
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                {new Date(date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Sector filter */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        <button
          onClick={() => setSelectedSector(null)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
            !selectedSector
              ? "bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900"
              : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
          }`}
        >
          All Sectors
        </button>
        {sectors.map((sector) => (
          <button
            key={sector}
            onClick={() => setSelectedSector(sector)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              selectedSector === sector
                ? "bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900"
                : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
            style={{
              borderLeft: `3px solid ${SECTOR_COLORS[sector] || '#gray'}`,
            }}
          >
            {sector} ({stocksBySector[sector].length})
          </button>
        ))}
      </div>

      {/* Heatmap grid */}
      {displayStocks.length > 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex flex-wrap gap-1">
            {displayStocks
              .sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))
              .map((stock) => {
                const isPositive = stock.changePercent >= 0;
                const absChange = Math.abs(stock.changePercent);

                // Calculate color intensity based on change (0-5% range)
                const intensity = Math.min(absChange / 5, 1);

                // Size based on market cap (relative to largest)
                const maxCap = Math.max(...displayStocks.map((s) => s.marketCap || 0));
                const minSize = 60;
                const maxSize = 150;
                const size = minSize + (maxSize - minSize) * ((stock.marketCap || 0) / maxCap);

                return (
                  <div
                    key={stock.symbol}
                    className="relative group cursor-pointer transition-transform hover:scale-105 hover:z-10"
                    style={{
                      width: `${size}px`,
                      height: `${size * 0.75}px`,
                      backgroundColor: isPositive
                        ? `rgba(34, 197, 94, ${0.2 + intensity * 0.8})`
                        : `rgba(239, 68, 68, ${0.2 + intensity * 0.8})`,
                    }}
                  >
                    <div className="absolute inset-0 flex flex-col items-center justify-center p-1">
                      <span className="text-xs font-bold text-gray-900 dark:text-white">
                        {stock.symbol}
                      </span>
                      <span
                        className={`text-xs font-semibold ${
                          isPositive ? 'text-green-900 dark:text-green-100' : 'text-red-900 dark:text-red-100'
                        }`}
                      >
                        {isPositive ? '+' : ''}{stock.changePercent.toFixed(1)}%
                      </span>
                    </div>

                    {/* Hover tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                      <div className="font-semibold">{stock.name}</div>
                      <div className="text-gray-400">{stock.symbol}</div>
                      <div className={isPositive ? 'text-green-400' : 'text-red-400'}>
                        {isPositive ? '+' : ''}{stock.changePercent.toFixed(2)}%
                      </div>
                      <div className="text-gray-300">
                        ${stock.price.toFixed(2)}
                      </div>
                      <div className="text-gray-400 text-xs">
                        Cap: ${((stock.marketCap || 0) / 1e9).toFixed(1)}B
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      ) : (
        <div className="p-12 text-center bg-gray-50 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
          <p className="text-gray-500 dark:text-gray-400">No heatmap data available for this date</p>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-sm text-gray-600 dark:text-gray-400">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-green-500 rounded"></div>
          <span>Positive</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-500 rounded"></div>
          <span>Negative</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs">Size = Market Cap</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs">Color Intensity = % Change</div>
        </div>
      </div>
    </div>
  );
}
