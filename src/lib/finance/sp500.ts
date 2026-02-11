// Major S&P 500 stocks grouped by sector
// This is a curated list of ~100 major stocks for the heatmap visualization

export interface SP500Stock {
  symbol: string;
  name: string;
  sector: string;
}

export const SP500_STOCKS: SP500Stock[] = [
  // Technology
  { symbol: 'AAPL', name: 'Apple', sector: 'Technology' },
  { symbol: 'MSFT', name: 'Microsoft', sector: 'Technology' },
  { symbol: 'NVDA', name: 'NVIDIA', sector: 'Technology' },
  { symbol: 'GOOGL', name: 'Alphabet', sector: 'Technology' },
  { symbol: 'META', name: 'Meta', sector: 'Technology' },
  { symbol: 'AVGO', name: 'Broadcom', sector: 'Technology' },
  { symbol: 'ORCL', name: 'Oracle', sector: 'Technology' },
  { symbol: 'CSCO', name: 'Cisco', sector: 'Technology' },
  { symbol: 'ADBE', name: 'Adobe', sector: 'Technology' },
  { symbol: 'CRM', name: 'Salesforce', sector: 'Technology' },
  { symbol: 'INTC', name: 'Intel', sector: 'Technology' },
  { symbol: 'AMD', name: 'AMD', sector: 'Technology' },
  { symbol: 'IBM', name: 'IBM', sector: 'Technology' },
  { symbol: 'QCOM', name: 'Qualcomm', sector: 'Technology' },
  { symbol: 'NOW', name: 'ServiceNow', sector: 'Technology' },

  // Consumer Discretionary
  { symbol: 'AMZN', name: 'Amazon', sector: 'Consumer Discretionary' },
  { symbol: 'TSLA', name: 'Tesla', sector: 'Consumer Discretionary' },
  { symbol: 'HD', name: 'Home Depot', sector: 'Consumer Discretionary' },
  { symbol: 'MCD', name: "McDonald's", sector: 'Consumer Discretionary' },
  { symbol: 'NKE', name: 'Nike', sector: 'Consumer Discretionary' },
  { symbol: 'SBUX', name: 'Starbucks', sector: 'Consumer Discretionary' },
  { symbol: 'LOW', name: "Lowe's", sector: 'Consumer Discretionary' },
  { symbol: 'TJX', name: 'TJX Companies', sector: 'Consumer Discretionary' },
  { symbol: 'BKNG', name: 'Booking Holdings', sector: 'Consumer Discretionary' },
  { symbol: 'CMG', name: 'Chipotle', sector: 'Consumer Discretionary' },

  // Communication Services
  { symbol: 'NFLX', name: 'Netflix', sector: 'Communication Services' },
  { symbol: 'DIS', name: 'Disney', sector: 'Communication Services' },
  { symbol: 'CMCSA', name: 'Comcast', sector: 'Communication Services' },
  { symbol: 'VZ', name: 'Verizon', sector: 'Communication Services' },
  { symbol: 'T', name: 'AT&T', sector: 'Communication Services' },
  { symbol: 'TMUS', name: 'T-Mobile', sector: 'Communication Services' },

  // Financials
  { symbol: 'BRK.B', name: 'Berkshire Hathaway', sector: 'Financials' },
  { symbol: 'JPM', name: 'JPMorgan Chase', sector: 'Financials' },
  { symbol: 'V', name: 'Visa', sector: 'Financials' },
  { symbol: 'MA', name: 'Mastercard', sector: 'Financials' },
  { symbol: 'BAC', name: 'Bank of America', sector: 'Financials' },
  { symbol: 'WFC', name: 'Wells Fargo', sector: 'Financials' },
  { symbol: 'GS', name: 'Goldman Sachs', sector: 'Financials' },
  { symbol: 'MS', name: 'Morgan Stanley', sector: 'Financials' },
  { symbol: 'AXP', name: 'American Express', sector: 'Financials' },
  { symbol: 'BLK', name: 'BlackRock', sector: 'Financials' },
  { symbol: 'C', name: 'Citigroup', sector: 'Financials' },
  { symbol: 'SCHW', name: 'Charles Schwab', sector: 'Financials' },

  // Healthcare
  { symbol: 'LLY', name: 'Eli Lilly', sector: 'Healthcare' },
  { symbol: 'UNH', name: 'UnitedHealth', sector: 'Healthcare' },
  { symbol: 'JNJ', name: 'Johnson & Johnson', sector: 'Healthcare' },
  { symbol: 'ABBV', name: 'AbbVie', sector: 'Healthcare' },
  { symbol: 'MRK', name: 'Merck', sector: 'Healthcare' },
  { symbol: 'PFE', name: 'Pfizer', sector: 'Healthcare' },
  { symbol: 'TMO', name: 'Thermo Fisher', sector: 'Healthcare' },
  { symbol: 'ABT', name: 'Abbott', sector: 'Healthcare' },
  { symbol: 'DHR', name: 'Danaher', sector: 'Healthcare' },
  { symbol: 'AMGN', name: 'Amgen', sector: 'Healthcare' },

  // Consumer Staples
  { symbol: 'WMT', name: 'Walmart', sector: 'Consumer Staples' },
  { symbol: 'PG', name: 'Procter & Gamble', sector: 'Consumer Staples' },
  { symbol: 'KO', name: 'Coca-Cola', sector: 'Consumer Staples' },
  { symbol: 'PEP', name: 'PepsiCo', sector: 'Consumer Staples' },
  { symbol: 'COST', name: 'Costco', sector: 'Consumer Staples' },
  { symbol: 'PM', name: 'Philip Morris', sector: 'Consumer Staples' },
  { symbol: 'MO', name: 'Altria', sector: 'Consumer Staples' },
  { symbol: 'CL', name: 'Colgate-Palmolive', sector: 'Consumer Staples' },

  // Energy
  { symbol: 'XOM', name: 'Exxon Mobil', sector: 'Energy' },
  { symbol: 'CVX', name: 'Chevron', sector: 'Energy' },
  { symbol: 'COP', name: 'ConocoPhillips', sector: 'Energy' },
  { symbol: 'SLB', name: 'Schlumberger', sector: 'Energy' },
  { symbol: 'EOG', name: 'EOG Resources', sector: 'Energy' },
  { symbol: 'MPC', name: 'Marathon Petroleum', sector: 'Energy' },

  // Industrials
  { symbol: 'BA', name: 'Boeing', sector: 'Industrials' },
  { symbol: 'UPS', name: 'UPS', sector: 'Industrials' },
  { symbol: 'HON', name: 'Honeywell', sector: 'Industrials' },
  { symbol: 'CAT', name: 'Caterpillar', sector: 'Industrials' },
  { symbol: 'GE', name: 'General Electric', sector: 'Industrials' },
  { symbol: 'MMM', name: '3M', sector: 'Industrials' },
  { symbol: 'LMT', name: 'Lockheed Martin', sector: 'Industrials' },
  { symbol: 'RTX', name: 'Raytheon', sector: 'Industrials' },

  // Materials
  { symbol: 'LIN', name: 'Linde', sector: 'Materials' },
  { symbol: 'APD', name: 'Air Products', sector: 'Materials' },
  { symbol: 'SHW', name: 'Sherwin-Williams', sector: 'Materials' },
  { symbol: 'FCX', name: 'Freeport-McMoRan', sector: 'Materials' },
  { symbol: 'NEM', name: 'Newmont', sector: 'Materials' },

  // Real Estate
  { symbol: 'AMT', name: 'American Tower', sector: 'Real Estate' },
  { symbol: 'PLD', name: 'Prologis', sector: 'Real Estate' },
  { symbol: 'CCI', name: 'Crown Castle', sector: 'Real Estate' },
  { symbol: 'EQIX', name: 'Equinix', sector: 'Real Estate' },
  { symbol: 'SPG', name: 'Simon Property', sector: 'Real Estate' },

  // Utilities
  { symbol: 'NEE', name: 'NextEra Energy', sector: 'Utilities' },
  { symbol: 'DUK', name: 'Duke Energy', sector: 'Utilities' },
  { symbol: 'SO', name: 'Southern Company', sector: 'Utilities' },
  { symbol: 'D', name: 'Dominion Energy', sector: 'Utilities' },
  { symbol: 'AEP', name: 'American Electric', sector: 'Utilities' },
];

// Sector colors for the heatmap
export const SECTOR_COLORS: Record<string, string> = {
  'Technology': '#3b82f6', // blue
  'Consumer Discretionary': '#8b5cf6', // purple
  'Communication Services': '#ec4899', // pink
  'Financials': '#10b981', // emerald
  'Healthcare': '#ef4444', // red
  'Consumer Staples': '#f59e0b', // amber
  'Energy': '#14b8a6', // teal
  'Industrials': '#6366f1', // indigo
  'Materials': '#84cc16', // lime
  'Real Estate': '#06b6d4', // cyan
  'Utilities': '#f97316', // orange
};

// DOW 30 constituent symbols
export const DOW_30_SYMBOLS = [
  'AAPL', 'AMGN', 'AXP', 'BA', 'CAT', 'CRM', 'CSCO', 'CVX',
  'DIS', 'DOW', 'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ',
  'JPM', 'KO', 'MCD', 'MMM', 'MRK', 'MSFT', 'NKE', 'PG',
  'TRV', 'UNH', 'V', 'VZ', 'WBA', 'WMT'
];

// NASDAQ-100 major constituent symbols (subset of most important ones)
export const NASDAQ_SYMBOLS = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO',
  'COST', 'NFLX', 'ADBE', 'PEP', 'CSCO', 'TMUS', 'CMCSA', 'INTC',
  'AMD', 'QCOM', 'INTU', 'TXN', 'AMAT', 'HON', 'AMGN', 'SBUX',
  'GILD', 'BKNG', 'ADP', 'ADI', 'MDLZ', 'ISRG', 'REGN', 'VRTX',
  'LRCX', 'PANW', 'MU', 'KLAC', 'SNPS', 'CDNS', 'MRVL', 'ORLY',
  'CTAS', 'ABNB', 'MELI', 'NXPI', 'WDAY', 'MNST', 'FTNT', 'DASH'
];

// Helper to get stocks for a specific index
export function getStocksForIndex(index: 'SP500' | 'NASDAQ' | 'DOW' | null): SP500Stock[] {
  if (!index) return SP500_STOCKS; // Return all if no filter

  if (index === 'DOW') {
    return SP500_STOCKS.filter(stock => DOW_30_SYMBOLS.includes(stock.symbol));
  }

  if (index === 'NASDAQ') {
    return SP500_STOCKS.filter(stock => NASDAQ_SYMBOLS.includes(stock.symbol));
  }

  // SP500 returns all
  return SP500_STOCKS;
}
