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
  const changeColor = isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400";

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4 animate-pulse">
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-16 mb-2" />
        <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-24 mb-2" />
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-20" />
      </div>
    );
  }

  if (error && !quote) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-red-200 dark:border-red-800 p-4">
        <div className="flex items-start justify-between mb-2">
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {item.symbol}
          </span>
          {onRemove && (
            <button
              onClick={() => onRemove(item.id)}
              className="text-red-500 hover:text-red-600 transition-colors"
              title="Remove from watchlist"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      </div>
    );
  }

  if (!quote) {
    return null;
  }

  return (
    <div
      className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-sky-300 dark:hover:border-sky-700 transition-all p-4 cursor-pointer group"
      onClick={() => onClick && onClick(item.symbol)}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
              {quote.symbol}
            </span>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {quote.exchange}
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
            {item.name}
          </p>
        </div>
        {onRemove && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove(item.id);
            }}
            className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-all"
            title="Remove from watchlist"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div className="mb-2">
        <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          ${quote.price.toFixed(2)}
        </div>
        <div className={`text-sm font-medium ${changeColor}`}>
          {isPositive ? "+" : ""}
          {quote.change.toFixed(2)} ({isPositive ? "+" : ""}
          {quote.changePercent.toFixed(2)}%)
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        {quote.marketState && (
          <span className={quote.marketState === 'REGULAR' ? 'text-green-600 dark:text-green-400' : ''}>
            {quote.marketState === 'REGULAR' ? '● Market Open' : 'Market Closed'}
          </span>
        )}
        {quote.volume && (
          <span>
            Vol: {(quote.volume / 1000000).toFixed(1)}M
          </span>
        )}
      </div>
    </div>
  );
}
