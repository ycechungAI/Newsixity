import YahooFinance from 'yahoo-finance2';
import type { StockQuote, ChartDataPoint, StockSearchResult, CompanyProfile } from './types';

// Initialize Yahoo Finance instance (v3 API)
const yahooFinance = new YahooFinance();

type YahooQuoteResult = {
  symbol?: string;
  longName?: string;
  shortName?: string;
  exchange?: string;
  exchangeName?: string;
  regularMarketPrice?: number;
  regularMarketChange?: number;
  regularMarketChangePercent?: number;
  regularMarketVolume?: number | null;
  marketCap?: number | null;
  currency?: string;
  fiftyTwoWeekHigh?: number | null;
  fiftyTwoWeekLow?: number | null;
  marketState?: 'PRE' | 'REGULAR' | 'POST' | 'CLOSED';
};

type YahooChartQuote = {
  date?: Date | string;
  close?: number | null;
  volume?: number | null;
};

type YahooChartResult = {
  quotes?: YahooChartQuote[] | null;
};

type YahooSearchQuote = {
  symbol?: string;
  shortname?: string;
  longname?: string;
  exchDisp?: string;
  exchange?: string;
  quoteType?: string;
};

type YahooSearchResult = {
  quotes?: YahooSearchQuote[] | null;
};

type YahooSummaryProfile = {
  longBusinessSummary?: string;
};

type YahooAssetProfile = YahooSummaryProfile & {
  sector?: string;
  industry?: string;
  website?: string;
  fullTimeEmployees?: number;
  country?: string;
};

type YahooPriceProfile = {
  longName?: string;
  shortName?: string;
};

type YahooQuoteSummaryResult = {
  assetProfile?: YahooAssetProfile;
  summaryProfile?: YahooSummaryProfile;
  price?: YahooPriceProfile;
};

// Fetch quote from Yahoo Finance
export async function fetchYahooQuote(symbol: string): Promise<StockQuote> {
  try {
    const result = await yahooFinance.quote(symbol) as YahooQuoteResult | null;

    if (!result) {
      throw new Error(`Stock ${symbol} not found (possibly delisted)`);
    }

    return {
      symbol: result.symbol || symbol,
      name: result.longName || result.shortName || symbol,
      exchange: result.exchange || result.exchangeName || 'UNKNOWN',
      price: result.regularMarketPrice || 0,
      change: result.regularMarketChange || 0,
      changePercent: result.regularMarketChangePercent || 0,
      volume: result.regularMarketVolume || null,
      marketCap: result.marketCap || null,
      currency: result.currency || 'USD',
      fiftyTwoWeekHigh: result.fiftyTwoWeekHigh || null,
      fiftyTwoWeekLow: result.fiftyTwoWeekLow || null,
      marketState: (result.marketState as 'PRE' | 'REGULAR' | 'POST' | 'CLOSED') || 'CLOSED',
    };
  } catch (error) {
    if (error instanceof Error && error.message.includes('404')) {
      throw new Error(`Stock ${symbol} has been delisted or does not exist`);
    }
    throw error;
  }
}

// Fetch chart data from Yahoo Finance
export async function fetchYahooChart(
  symbol: string,
  period1: Date,
  period2: Date,
  interval: '1d' | '1h' | '5m' = '1d'
): Promise<ChartDataPoint[]> {
  try {
    const result = await yahooFinance.chart(symbol, {
      period1,
      period2,
      interval,
    }) as YahooChartResult | null;

    if (!result || !result.quotes || result.quotes.length === 0) {
      return [];
    }

    return result.quotes.map((quote) => ({
      date: (quote.date instanceof Date
        ? quote.date
        : new Date(quote.date ?? Date.now())).toISOString(),
      price: quote.close || 0,
      volume: quote.volume ?? undefined,
    }));
  } catch (error) {
    console.error(`[Newsixity] Failed to fetch chart for ${symbol}:`, error);
    return [];
  }
}

// Search for stocks by query
export async function searchYahooStocks(query: string): Promise<StockSearchResult[]> {
  try {
    const results = await yahooFinance.search(query) as YahooSearchResult | null;

    if (!results || !results.quotes || results.quotes.length === 0) {
      return [];
    }

    return results.quotes
      .filter((quote) => quote.symbol && quote.shortname)
      .map((quote) => ({
        symbol: quote.symbol ?? "",
        name: quote.shortname || quote.longname || quote.symbol || "",
        exchange: quote.exchDisp || quote.exchange || 'UNKNOWN',
        type: quote.quoteType || 'EQUITY',
      }))
      .slice(0, 10); // Limit to top 10 results
  } catch (error) {
    console.error('[Newsixity] Failed to search stocks:', error);
    return [];
  }
}

// Get company profile from Yahoo Finance
export async function fetchYahooProfile(symbol: string): Promise<CompanyProfile> {
  try {
    const result = await yahooFinance.quoteSummary(symbol, {
      modules: ['assetProfile', 'summaryProfile', 'price'],
    }) as YahooQuoteSummaryResult;

    const assetProfile = result.assetProfile;
    const summaryProfile = result.summaryProfile;
    const price = result.price;

    return {
      symbol,
      name: price?.longName || price?.shortName || symbol,
      description: assetProfile?.longBusinessSummary || summaryProfile?.longBusinessSummary || '',
      sector: assetProfile?.sector || null,
      industry: assetProfile?.industry || null,
      website: assetProfile?.website || null,
      employees: assetProfile?.fullTimeEmployees || null,
      country: assetProfile?.country || null,
    };
  } catch (error) {
    console.error(`[Newsixity] Failed to fetch profile for ${symbol}:`, error);
    throw new Error(`Failed to fetch company profile for ${symbol}`);
  }
}

// Batch fetch quotes for multiple symbols
export async function fetchYahooQuotes(symbols: string[]): Promise<Map<string, StockQuote>> {
  const quotes = new Map<string, StockQuote>();

  // Fetch in parallel but handle errors individually
  const results = await Promise.allSettled(
    symbols.map((symbol) => fetchYahooQuote(symbol))
  );

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      quotes.set(symbols[index], result.value);
    } else {
      console.error(`[Newsixity] Failed to fetch quote for ${symbols[index]}:`, result.reason);
    }
  });

  return quotes;
}
