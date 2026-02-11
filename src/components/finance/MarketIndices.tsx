"use client";

import { useState, useEffect } from "react";
import { getQuotes } from "@/lib/finance/api";
import { MARKET_INDICES } from "@/lib/finance/constants";
import type { StockQuote } from "@/lib/finance/types";

interface MarketIndicesProps {
  onIndexClick?: (index: 'SP500' | 'NASDAQ' | 'DOW') => void;
  selectedIndex?: 'SP500' | 'NASDAQ' | 'DOW' | null;
}

export default function MarketIndices({ onIndexClick, selectedIndex }: MarketIndicesProps) {
  const [indices, setIndices] = useState<StockQuote[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadIndices();
  }, []);

  async function loadIndices() {
    try {
      const symbols = MARKET_INDICES.map((idx) => idx.symbol);
      const quotes = await getQuotes(symbols);
      setIndices(quotes);
    } catch (error) {
      console.error("[Newsixity] Failed to load market indices:", error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {indices.map((quote) => {
        const isPositive = quote.change >= 0;
        const indexKey =
          quote.symbol === "^GSPC" ? "SP500" :
          quote.symbol === "^IXIC" ? "NASDAQ" :
          quote.symbol === "^DJI" ? "DOW" : null;
        const displayName =
          quote.symbol === "^GSPC" ? "S&P 500" :
          quote.symbol === "^IXIC" ? "NASDAQ" :
          quote.symbol === "^DJI" ? "DOW" :
          quote.name;
        const isSelected = selectedIndex === indexKey;

        return (
          <button
            key={quote.symbol}
            onClick={() => indexKey && onIndexClick?.(indexKey as 'SP500' | 'NASDAQ' | 'DOW')}
            className={`p-4 bg-white dark:bg-gray-800 rounded-lg border transition-all text-left ${
              isSelected
                ? "border-sky-500 dark:border-sky-400 ring-2 ring-sky-500 ring-opacity-50 dark:ring-sky-400"
                : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 cursor-pointer"
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                  {displayName}
                </p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">
                  {quote.price.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </p>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1 text-sm font-medium ${
                      isPositive
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {isPositive ? "▲" : "▼"}
                    {Math.abs(quote.change).toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                  <span
                    className={`text-sm font-medium ${
                      isPositive
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    ({isPositive ? "+" : ""}
                    {quote.changePercent.toFixed(2)}%)
                  </span>
                </div>
              </div>
              {/* Mini trend indicator */}
              <div
                className={`w-2 h-2 rounded-full ${
                  isPositive ? "bg-green-500" : "bg-red-500"
                }`}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
}
