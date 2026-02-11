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

export default function FinanceDashboard() {
  const [watchlist, setWatchlist] = useState<WatchlistItemWithQuote[]>([]);
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<'SP500' | 'NASDAQ' | 'DOW' | null>('SP500');

  // Load watchlist on mount
  useEffect(() => {
    loadWatchlist();
  }, []);

  async function loadWatchlist() {
    try {
      const data = await getWatchlist();

      // If watchlist is empty, add default stocks
      if (data.length === 0) {
        console.log("[Newsixity] Watchlist is empty, adding default stocks...");
        await Promise.allSettled(
          DEFAULT_STOCKS.map((stock) =>
            addToWatchlist(stock.symbol, stock.name, stock.exchange)
          )
        );
        // Reload after adding defaults
        const newData = await getWatchlist();
        setWatchlist(newData);
      } else {
        setWatchlist(data);
      }
    } catch (e) {
      console.error("[Newsixity] Failed to load watchlist:", e);
      setError(e instanceof Error ? e.message : "Failed to load watchlist");
    } finally {
      setInitialLoading(false);
    }
  }

  async function handleAddStock(stock: StockSearchResult) {
    try {
      // Add loading state
      const newItem: WatchlistItemWithQuote = {
        id: 0, // Temporary ID
        symbol: stock.symbol,
        name: stock.name,
        exchange: stock.exchange,
        addedAt: new Date().toISOString(),
        quote: null,
        loading: true,
        error: null,
      };

      setWatchlist((prev) => [newItem, ...prev]);

      // Add to database
      await addToWatchlist(stock.symbol, stock.name, stock.exchange);

      // Reload watchlist to get quote and real ID
      await loadWatchlist();
    } catch (e) {
      console.error("[Newsixity] Failed to add stock:", e);
      alert(e instanceof Error ? e.message : "Failed to add stock");
      // Remove the temporary item
      setWatchlist((prev) => prev.filter((item) => item.symbol !== stock.symbol));
    }
  }

  async function handleRemoveStock(id: number) {
    if (!confirm("Remove this stock from your watchlist?")) {
      return;
    }

    try {
      await removeFromWatchlist(id);
      setWatchlist((prev) => prev.filter((item) => item.id !== id));
    } catch (e) {
      console.error("[Newsixity] Failed to remove stock:", e);
      alert("Failed to remove stock");
    }
  }

  async function handleRefresh() {
    setInitialLoading(true);
    await loadWatchlist();
    setInitialLoading(false);
  }

  if (initialLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="h-8 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-10 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
        <p className="text-sm text-red-600 dark:text-red-400 mb-2">{error}</p>
        <button
          onClick={handleRefresh}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Finance</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Market overview and watchlist
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title="Refresh quotes"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <StockSearch onStockSelect={handleAddStock} />
        </div>
      </div>

      {/* Market Indices */}
      <MarketIndices
        onIndexClick={setSelectedIndex}
        selectedIndex={selectedIndex}
      />

      {/* Market Heatmap */}
      <div className="pt-2">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {selectedIndex === 'DOW' ? 'DOW 30' : selectedIndex === 'NASDAQ' ? 'NASDAQ-100' : 'S&P 500'} Heatmap
          </h2>
          {selectedIndex && (
            <button
              onClick={() => setSelectedIndex(null)}
              className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
            >
              Show All
            </button>
          )}
        </div>
        <MarketHeatmap indexFilter={selectedIndex} />
      </div>

      {/* Watchlist Header */}
      <div className="flex items-center justify-between pt-2">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          My Watchlist
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {watchlist.length} stock{watchlist.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Stock grid */}
      {watchlist.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {watchlist.map((item) => (
            <StockCard
              key={item.id}
              item={item}
              onRemove={handleRemoveStock}
              onClick={setSelectedStock}
            />
          ))}
        </div>
      ) : (
        <div className="p-12 text-center bg-gray-50 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
          <svg
            className="w-12 h-12 mx-auto mb-4 text-gray-400 dark:text-gray-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"
            />
          </svg>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
            No stocks in watchlist
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Search for stocks above to add them to your watchlist
          </p>
        </div>
      )}

      {/* Chart modal */}
      {selectedStock && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => setSelectedStock(null)}
        >
          <div
            className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 p-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                {selectedStock}
              </h2>
              <button
                onClick={() => setSelectedStock(null)}
                className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6">
              <StockChart symbol={selectedStock} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
