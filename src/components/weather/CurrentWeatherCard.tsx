"use client";

import type { CurrentWeather, DailyForecast } from "@/lib/weather/types";
import { getWeatherInfo } from "@/lib/weather/codes";

interface CurrentWeatherCardProps {
  cityName: string;
  country: string;
  current: CurrentWeather;
  daily: DailyForecast;
  loading: boolean;
}

export default function CurrentWeatherCard({
  cityName,
  country,
  current,
  daily,
  loading,
}: CurrentWeatherCardProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm overflow-hidden animate-pulse">
        <div className="h-2 bg-gradient-to-r from-sky-500 to-blue-600 rounded-t-xl" />
        <div className="p-6">
          <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-48 mb-6" />
          <div className="flex items-center gap-6 mb-6">
            <div className="w-20 h-20 bg-gray-200 dark:bg-gray-700 rounded-full" />
            <div className="space-y-2">
              <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded w-32" />
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24" />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const weatherInfo = getWeatherInfo(current.weather_code);
  const todayHigh = daily.temperature_2m_max[0];
  const todayLow = daily.temperature_2m_min[0];

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm overflow-hidden">
      {/* Accent gradient bar */}
      <div className="h-2 bg-gradient-to-r from-sky-500 to-blue-600" />

      <div className="p-6">
        {/* City name */}
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          {cityName}, {country}
        </h2>

        {/* Main weather display */}
        <div className="flex items-center gap-6 mb-6">
          <span className="text-6xl" role="img" aria-label={weatherInfo.label}>
            {weatherInfo.emoji}
          </span>
          <div>
            <p className="text-5xl font-bold text-gray-900 dark:text-gray-100">
              {Math.round(current.temperature_2m)}°C
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {weatherInfo.label}
            </p>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Feels Like</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {Math.round(current.apparent_temperature)}°C
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Humidity</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {current.relative_humidity_2m}%
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Wind</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {Math.round(current.wind_speed_10m)} km/h
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">High / Low</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {Math.round(todayHigh)}° / {Math.round(todayLow)}°
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
