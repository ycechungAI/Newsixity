"use client";

import type { DailyForecast } from "@/lib/weather/types";
import { getWeatherInfo } from "@/lib/weather/codes";

interface ForecastCardProps {
  cityName: string;
  country: string;
  daily: DailyForecast;
  loading: boolean;
  onRemove?: () => void;
}

const CloseIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path d="M6 18L18 6M6 6l12 12" />
  </svg>
);

function getDayName(dateString: string): string {
  const date = new Date(dateString + "T00:00:00");
  return date.toLocaleDateString("en-US", { weekday: "short" });
}

export default function ForecastCard({
  cityName,
  country,
  daily,
  loading,
  onRemove,
}: ForecastCardProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm p-5 animate-pulse">
        <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-40 mb-4" />
        <div className="grid grid-cols-7 gap-2">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="space-y-2 text-center">
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded mx-auto w-8" />
              <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded-full mx-auto w-6" />
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded mx-auto w-6" />
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded mx-auto w-6" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {cityName}, {country}
        </h3>
        {onRemove && (
          <button
            onClick={onRemove}
            className="p-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title="Remove city"
          >
            <CloseIcon />
          </button>
        )}
      </div>

      {/* 7-day grid */}
      <div className="grid grid-cols-7 gap-1 text-center">
        {/* Day names */}
        {daily.time.map((date, i) => (
          <div key={date} className="space-y-1.5">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">
              {i === 0 ? "Today" : getDayName(date)}
            </p>
            <p className="text-lg" role="img" aria-label={getWeatherInfo(daily.weather_code[i]).label}>
              {getWeatherInfo(daily.weather_code[i]).emoji}
            </p>
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {Math.round(daily.temperature_2m_max[i])}°
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {Math.round(daily.temperature_2m_min[i])}°
            </p>
            {daily.precipitation_sum[i] > 0 && (
              <p className="text-[10px] text-blue-500 dark:text-blue-400">
                {daily.precipitation_sum[i].toFixed(1)}mm
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
