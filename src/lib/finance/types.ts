// Stock quote data from Yahoo Finance
export interface StockQuote {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number | null;
  marketCap: number | null;
  currency: string;
  fiftyTwoWeekHigh: number | null;
  fiftyTwoWeekLow: number | null;
  marketState: 'PRE' | 'REGULAR' | 'POST' | 'CLOSED';
}

// Chart data point
export interface ChartDataPoint {
  date: string; // ISO 8601
  price: number;
  volume?: number;
}

// Chart response with metadata
export interface ChartResponse {
  symbol: string;
  timeframe: string;
  data: ChartDataPoint[];
  cached: boolean;
}

// Company profile information
export interface CompanyProfile {
  symbol: string;
  name: string;
  description: string;
  sector: string | null;
  industry: string | null;
  website: string | null;
  employees: number | null;
  country: string | null;
}

// Financial metrics
export interface FinancialMetrics {
  symbol: string;
  peRatio: number | null;
  eps: number | null;
  marketCap: number | null;
  dividendYield: number | null;
  beta: number | null;
}

// Stock search result
export interface StockSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string; // 'EQUITY', 'ETF', 'MUTUALFUND', etc.
}

// Watchlist item from database
export interface WatchlistItem {
  id: number;
  symbol: string;
  name: string;
  exchange: string | null;
  addedAt: string;
}

// Watchlist item with quote data (for UI)
export interface WatchlistItemWithQuote extends WatchlistItem {
  quote: StockQuote | null;
  loading: boolean;
  error: string | null;
}

// Cached quote from database
export interface CachedQuote {
  id: number;
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number | null;
  marketCap: number | null;
  currency: string | null;
  cachedAt: string;
  expiresAt: string;
}

// Cached chart from database
export interface CachedChart {
  id: number;
  symbol: string;
  timeframe: string;
  data: string; // JSON string of ChartDataPoint[]
  cachedAt: string;
  expiresAt: string;
}

// Heatmap stock data (quote with sector info)
export interface HeatmapStock extends StockQuote {
  sector: string;
}

// Heatmap snapshot from database
export interface HeatmapSnapshot {
  id: number;
  date: string; // YYYY-MM-DD format
  data: string; // JSON string of HeatmapStock[]
  createdAt: string;
}

// Heatmap snapshot API response
export interface HeatmapSnapshotResponse {
  date: string;
  stocks: HeatmapStock[];
  cached: boolean;
}
