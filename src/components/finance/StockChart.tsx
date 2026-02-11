"use client";

import { useState, useEffect } from "react";
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

  useEffect(() => {
    loadChart();
  }, [symbol, timeframe]);

  async function loadChart() {
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
  }

  if (loading) {
    return (
      <div className="w-full h-64 bg-gray-50 dark:bg-gray-800 rounded-lg flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-sky-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-64 bg-gray-50 dark:bg-gray-800 rounded-lg flex flex-col items-center justify-center gap-2">
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        <button
          onClick={loadChart}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-sky-500 text-white hover:bg-sky-600 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="w-full h-64 bg-gray-50 dark:bg-gray-800 rounded-lg flex items-center justify-center">
        <p className="text-sm text-gray-500 dark:text-gray-400">No chart data available</p>
      </div>
    );
  }

  // Calculate min/max for scaling
  const prices = data.map((d) => d.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceRange = maxPrice - minPrice;

  const firstPrice = data[0].price;
  const lastPrice = data[data.length - 1].price;
  const change = lastPrice - firstPrice;
  const changePercent = (change / firstPrice) * 100;
  const isPositive = change >= 0;

  // SVG dimensions
  const width = 800;
  const height = 300;
  const padding = 40;

  // Generate SVG path
  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((d.price - minPrice) / priceRange) * (height - 2 * padding);
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(" L ")}`;
  const areaD = `${pathD} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`;

  return (
    <div className="space-y-4">
      {/* Timeframe selector */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {CHART_TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              onClick={() => setTimeframe(tf.value)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                timeframe === tf.value
                  ? "bg-sky-500 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>
        <div className={`text-sm font-medium ${isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
          {isPositive ? "+" : ""}
          {change.toFixed(2)} ({isPositive ? "+" : ""}
          {changePercent.toFixed(2)}%)
        </div>
      </div>

      {/* Chart */}
      <div className="w-full bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Grid lines */}
          <g stroke="currentColor" strokeWidth="1" className="text-gray-200 dark:text-gray-700" opacity="0.3">
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
              const y = height - padding - ratio * (height - 2 * padding);
              return (
                <line
                  key={ratio}
                  x1={padding}
                  y1={y}
                  x2={width - padding}
                  y2={y}
                />
              );
            })}
          </g>

          {/* Area fill */}
          <path
            d={areaD}
            fill={isPositive ? "rgb(34, 197, 94)" : "rgb(239, 68, 68)"}
            opacity="0.1"
          />

          {/* Line */}
          <path
            d={pathD}
            fill="none"
            stroke={isPositive ? "rgb(34, 197, 94)" : "rgb(239, 68, 68)"}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}
