import type { StockQuote, ChartResponse, StockSearchResult, WatchlistItemWithQuote, HeatmapSnapshotResponse } from './types';

// Search for stocks
export async function searchStocks(query: string): Promise<StockSearchResult[]> {
  const response = await fetch(`/api/finance/search?query=${encodeURIComponent(query)}`);

  if (!response.ok) {
    throw new Error('Failed to search stocks');
  }

  const data = await response.json();
  return data.results || [];
}

// Get quote for a single symbol
export async function getQuote(symbol: string): Promise<StockQuote> {
  const response = await fetch(`/api/finance/quote?symbols=${encodeURIComponent(symbol)}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch quote for ${symbol}`);
  }

  const data = await response.json();
  return data.quotes[0];
}

// Get quotes for multiple symbols
export async function getQuotes(symbols: string[]): Promise<StockQuote[]> {
  const symbolsParam = symbols.map(s => encodeURIComponent(s)).join(',');
  const response = await fetch(`/api/finance/quote?symbols=${symbolsParam}`);

  if (!response.ok) {
    throw new Error('Failed to fetch quotes');
  }

  const data = await response.json();
  return data.quotes || [];
}

// Get chart data
export async function getChart(
  symbol: string,
  timeframe: '1d' | '5d' | '1mo' | '3mo' | '1y'
): Promise<ChartResponse> {
  const response = await fetch(
    `/api/finance/chart?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch chart for ${symbol}`);
  }

  return response.json();
}

// Get watchlist
export async function getWatchlist(): Promise<WatchlistItemWithQuote[]> {
  const response = await fetch('/api/finance/watchlist');

  if (!response.ok) {
    throw new Error('Failed to fetch watchlist');
  }

  const data = await response.json();
  return data.watchlist || [];
}

// Add stock to watchlist
export async function addToWatchlist(
  symbol: string,
  name: string,
  exchange: string
): Promise<void> {
  const response = await fetch('/api/finance/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, name, exchange }),
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error || 'Failed to add to watchlist');
  }
}

// Remove stock from watchlist
export async function removeFromWatchlist(id: number): Promise<void> {
  const response = await fetch('/api/finance/watchlist', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });

  if (!response.ok) {
    throw new Error('Failed to remove from watchlist');
  }
}

// Get heatmap snapshot for a specific date
export async function getHeatmapSnapshot(date?: string): Promise<HeatmapSnapshotResponse> {
  const url = date
    ? `/api/finance/heatmap?date=${encodeURIComponent(date)}`
    : '/api/finance/heatmap';

  const response = await fetch(url, { cache: 'no-store' });

  if (!response.ok) {
    throw new Error('Failed to fetch heatmap data');
  }

  return response.json();
}

// Get list of available heatmap dates
export async function getHeatmapDates(): Promise<string[]> {
  const response = await fetch('/api/finance/heatmap?list=true', { cache: 'no-store' });

  if (!response.ok) {
    throw new Error('Failed to fetch heatmap dates');
  }

  const data = await response.json();
  return data.dates || [];
}
