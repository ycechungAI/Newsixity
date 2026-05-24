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

  async function loadIndices() {
    try {
      const symbols = MARKET_INDICES.map((idx) => idx.symbol);
      setIndices(await getQuotes(symbols));
    } catch (e) {
      console.error("[Newsixity] Failed to load market indices:", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { 
    const timer = setTimeout(() => {
      loadIndices(); 
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div className="fin-indices">
        {[1, 2, 3].map((i) => (
          <div key={i} className="fin-index-btn" style={{ opacity: 0.4, minHeight: 64 }} />
        ))}
      </div>
    );
  }

  return (
    <div className="fin-indices">
      {indices.map((quote) => {
        const isPositive = quote.change >= 0;
        const indexKey =
          quote.symbol === "^GSPC" ? "SP500" :
          quote.symbol === "^IXIC" ? "NASDAQ" :
          quote.symbol === "^DJI"  ? "DOW" : null;
        const displayName =
          quote.symbol === "^GSPC" ? "S&P 500" :
          quote.symbol === "^IXIC" ? "NASDAQ" :
          quote.symbol === "^DJI"  ? "DOW" : quote.name;
        const isSelected = selectedIndex === indexKey;

        return (
          <button
            key={quote.symbol}
            className={`fin-index-btn${isSelected ? " active" : ""}`}
            onClick={() => indexKey && onIndexClick?.(indexKey as 'SP500' | 'NASDAQ' | 'DOW')}
          >
            <div className="fin-index-name">{displayName}</div>
            <div className="fin-index-price">
              {quote.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className={`fin-index-chg ${isPositive ? "pos" : "neg"}`}>
              <span className="fin-dot" style={{ background: isPositive ? "#16a34a" : "#dc2626" }} />
              {isPositive ? "▲" : "▼"}
              {Math.abs(quote.change).toFixed(2)}
              <span>({isPositive ? "+" : ""}{quote.changePercent.toFixed(2)}%)</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
