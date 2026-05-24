"use client";

import { useState, useEffect, useCallback } from "react";
import { getChart } from "@/lib/finance/api";
import type { ChartDataPoint } from "@/lib/finance/types";
import { CHART_TIMEFRAMES, type ChartTimeframe } from "@/lib/finance/constants";

interface StockChartProps {
  symbol: string;
}

export default function StockChart({ symbol }: StockChartProps) {
  const [timeframe, setTimeframe] = useState<ChartTimeframe>("1mo");
  const [data, setData] = useState<ChartDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadChart = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getChart(symbol, timeframe);
      setData(response.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chart");
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => { 
    const timer = setTimeout(() => {
      void loadChart(); 
    }, 0);
    return () => clearTimeout(timer);
  }, [loadChart]);

  if (loading) {
    return <div style={{ height: 200, background: "var(--surface)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", fontSize: 11 }}>Loading…</div>;
  }

  if (error) {
    return (
      <div style={{ height: 200, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8 }}>
        <div style={{ fontSize: 11, color: "#ef4444" }}>{error}</div>
        <button className="tb-btn" onClick={loadChart}>Retry</button>
      </div>
    );
  }

  if (data.length === 0) {
    return <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", fontSize: 11 }}>No chart data</div>;
  }

  const prices = data.map(d => d.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceRange = maxPrice - minPrice || 1;

  const firstPrice = data[0].price;
  const lastPrice = data[data.length - 1].price;
  const change = lastPrice - firstPrice;
  const changePercent = (change / firstPrice) * 100;
  const isPositive = change >= 0;
  const lineColor = isPositive ? "#16a34a" : "#dc2626";

  const W = 800, H = 280, P = 36;
  const points = data.map((d, i) => {
    const x = P + (i / (data.length - 1)) * (W - 2 * P);
    const y = H - P - ((d.price - minPrice) / priceRange) * (H - 2 * P);
    return `${x},${y}`;
  });
  const pathD = `M ${points.join(" L ")}`;
  const areaD = `${pathD} L ${W - P},${H - P} L ${P},${H - P} Z`;

  return (
    <div>
      <div className="fin-chart-header">
        <div className="fin-tf-bar">
          {CHART_TIMEFRAMES.map(tf => (
            <button
              key={tf.value}
              className={`fin-tf-btn${timeframe === tf.value ? " active" : ""}`}
              onClick={() => setTimeframe(tf.value)}
            >
              {tf.label}
            </button>
          ))}
        </div>
        <div className={`fin-chart-chg ${isPositive ? "pos" : "neg"}`}>
          {isPositive ? "+" : ""}{change.toFixed(2)} ({isPositive ? "+" : ""}{changePercent.toFixed(2)}%)
        </div>
      </div>
      <div className="fin-chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }} preserveAspectRatio="xMidYMid meet">
          <g stroke="var(--border)" strokeWidth="1" opacity="0.5">
            {[0, 0.25, 0.5, 0.75, 1].map(r => {
              const y = H - P - r * (H - 2 * P);
              return <line key={r} x1={P} y1={y} x2={W - P} y2={y} />;
            })}
          </g>
          <path d={areaD} fill={lineColor} opacity="0.08" />
          <path d={pathD} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}
