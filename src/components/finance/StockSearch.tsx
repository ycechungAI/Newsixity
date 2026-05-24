"use client";

import { useState, useRef, useEffect } from "react";
import { searchStocks } from "@/lib/finance/api";
import type { StockSearchResult } from "@/lib/finance/types";

interface StockSearchProps {
  onStockSelect: (stock: StockSearchResult) => void;
}

export default function StockSearch({ onStockSelect }: StockSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowResults(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (query.trim().length === 0) { 
      const timer = setTimeout(() => {
        setResults([]); 
        setShowResults(false); 
      }, 0);
      return () => clearTimeout(timer);
    }
    timeoutRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        setResults(await searchStocks(query));
        setShowResults(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); };
  }, [query]);

  function handleSelect(stock: StockSearchResult) {
    onStockSelect(stock);
    setQuery("");
    setResults([]);
    setShowResults(false);
  }

  return (
    <div ref={searchRef} className="fin-search">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={loading ? "Searching…" : "Add stock…"}
        className="fin-search-input"
      />
      {showResults && (results.length > 0 ? (
        <div className="fin-search-results">
          {results.map((stock) => (
            <button key={stock.symbol} className="fin-search-item" onClick={() => handleSelect(stock)}>
              <div>
                <span className="fin-search-sym">{stock.symbol}</span>
                <span className="fin-search-exch">{stock.exchange}</span>
              </div>
              <div className="fin-search-name">{stock.name}</div>
            </button>
          ))}
        </div>
      ) : !loading && query.trim().length > 0 ? (
        <div className="fin-search-results">
          <div className="fin-search-item" style={{ color: "var(--muted)", cursor: "default" }}>
            No results for &ldquo;{query}&rdquo;
          </div>
        </div>
      ) : null)}
    </div>
  );
}
