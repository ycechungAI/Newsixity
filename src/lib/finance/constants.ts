import type { StockSearchResult } from "./types";

// Default stocks to show if watchlist is empty
export const DEFAULT_STOCKS: StockSearchResult[] = [
  { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', type: 'EQUITY' },
  { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ', type: 'EQUITY' },
  { symbol: 'MSFT', name: 'Microsoft Corporation', exchange: 'NASDAQ', type: 'EQUITY' },
  { symbol: 'TSLA', name: 'Tesla, Inc.', exchange: 'NASDAQ', type: 'EQUITY' },
  { symbol: 'AMZN', name: 'Amazon.com, Inc.', exchange: 'NASDAQ', type: 'EQUITY' },
  { symbol: 'META', name: 'Meta Platforms, Inc.', exchange: 'NASDAQ', type: 'EQUITY' },
];

// Market indices to track
export const MARKET_INDICES: StockSearchResult[] = [
  { symbol: '^GSPC', name: 'S&P 500', exchange: 'INDEX', type: 'INDEX' },
  { symbol: '^IXIC', name: 'NASDAQ Composite', exchange: 'INDEX', type: 'INDEX' },
  { symbol: '^DJI', name: 'Dow Jones Industrial Average', exchange: 'INDEX', type: 'INDEX' },
];

// Cache time-to-live values (in minutes/hours)
export const QUOTE_CACHE_MINUTES = 15; // 15 minutes for delayed quotes
export const CHART_CACHE_HOURS_DAILY = 24; // 24 hours for daily data
export const CHART_CACHE_HOURS_INTRADAY = 1; // 1 hour for intraday data
export const PROFILE_CACHE_DAYS = 7; // 7 days for company profiles

// Chart timeframe options
export const CHART_TIMEFRAMES = [
  { value: '1d', label: '1 Day' },
  { value: '5d', label: '5 Days' },
  { value: '1mo', label: '1 Month' },
  { value: '3mo', label: '3 Months' },
  { value: '1y', label: '1 Year' },
] as const;

export type ChartTimeframe = typeof CHART_TIMEFRAMES[number]['value'];
