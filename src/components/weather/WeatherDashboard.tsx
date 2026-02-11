"use client";

import { useState, useEffect, useCallback } from "react";
import type { CityConfig, CityWeatherData, ForecastResponse } from "@/lib/weather/types";
import { fetchForecast } from "@/lib/weather/api";
import { DEFAULT_CITIES, LOCAL_CITY } from "@/lib/weather/constants";
import CurrentWeatherCard from "./CurrentWeatherCard";
import ForecastCard from "./ForecastCard";
import CitySearch from "./CitySearch";

function cityKey(city: CityConfig): string {
  return `${city.latitude},${city.longitude}`;
}

export default function WeatherDashboard() {
  const [cityForecasts, setCityForecasts] = useState<Map<string, CityWeatherData>>(new Map());
  const [additionalCities, setAdditionalCities] = useState<CityConfig[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch weather for all default cities on mount
  useEffect(() => {
    async function loadDefaultWeather() {
      setInitialLoading(true);
      setError(null);

      try {
        const results = await Promise.allSettled(
          DEFAULT_CITIES.map((city) => fetchForecast(city.latitude, city.longitude))
        );

        const dataMap = new Map<string, CityWeatherData>();

        results.forEach((result, index) => {
          const city = DEFAULT_CITIES[index];
          const key = cityKey(city);

          if (result.status === "fulfilled") {
            dataMap.set(key, {
              city,
              forecast: result.value,
              loading: false,
              error: null,
            });
          } else {
            dataMap.set(key, {
              city,
              forecast: null,
              loading: false,
              error: result.reason?.message ?? "Failed to load",
            });
          }
        });

        setCityForecasts(dataMap);
      } catch {
        setError("Failed to load weather data");
      } finally {
        setInitialLoading(false);
      }
    }

    loadDefaultWeather();
  }, []);

  // Add a city from search
  const handleCitySelect = useCallback(
    async (city: CityConfig) => {
      const key = cityKey(city);

      // Check for duplicates
      if (cityForecasts.has(key)) return;

      setAdditionalCities((prev) => [...prev, city]);

      // Add placeholder with loading state
      setCityForecasts((prev) => {
        const next = new Map(prev);
        next.set(key, { city, forecast: null, loading: true, error: null });
        return next;
      });

      try {
        const forecast = await fetchForecast(city.latitude, city.longitude);
        setCityForecasts((prev) => {
          const next = new Map(prev);
          next.set(key, { city, forecast, loading: false, error: null });
          return next;
        });
      } catch {
        setCityForecasts((prev) => {
          const next = new Map(prev);
          next.set(key, {
            city,
            forecast: null,
            loading: false,
            error: "Failed to load weather",
          });
          return next;
        });
      }
    },
    [cityForecasts]
  );

  // Remove a user-added city
  const handleCityRemove = useCallback((city: CityConfig) => {
    const key = cityKey(city);
    setAdditionalCities((prev) => prev.filter((c) => cityKey(c) !== key));
    setCityForecasts((prev) => {
      const next = new Map(prev);
      next.delete(key);
      return next;
    });
  }, []);

  // Get local city weather data
  const localData = cityForecasts.get(cityKey(LOCAL_CITY));

  // All cities for forecast cards (default + additional)
  const allCities = [...DEFAULT_CITIES, ...additionalCities];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Weather
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Current conditions and 7-day forecasts
          </p>
        </div>
        <div className="w-full sm:w-72">
          <CitySearch onCitySelect={handleCitySelect} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-lg border-l-4 border-red-500 bg-red-50 dark:bg-red-900/20 p-4">
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Current weather hero card for local city */}
      <div className="mb-6">
        <CurrentWeatherCard
          cityName={LOCAL_CITY.name}
          country={LOCAL_CITY.country}
          current={localData?.forecast?.current ?? {
            temperature_2m: 0,
            relative_humidity_2m: 0,
            apparent_temperature: 0,
            weather_code: 0,
            wind_speed_10m: 0,
          }}
          daily={localData?.forecast?.daily ?? {
            time: [],
            temperature_2m_max: [],
            temperature_2m_min: [],
            weather_code: [],
            precipitation_sum: [],
            wind_speed_10m_max: [],
          }}
          loading={initialLoading || (localData?.loading ?? true)}
        />
      </div>

      {/* Forecast cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {allCities.map((city) => {
          const key = cityKey(city);
          const data = cityForecasts.get(key);
          const isAdditional = additionalCities.some((c) => cityKey(c) === key);

          if (data?.error) {
            return (
              <div
                key={key}
                className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm p-5"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {city.name}, {city.country}
                  </h3>
                  {isAdditional && (
                    <button
                      onClick={() => handleCityRemove(city)}
                      className="p-1 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
                <p className="text-sm text-red-500 dark:text-red-400">{data.error}</p>
              </div>
            );
          }

          return (
            <ForecastCard
              key={key}
              cityName={city.name}
              country={city.country}
              daily={data?.forecast?.daily ?? {
                time: [],
                temperature_2m_max: [],
                temperature_2m_min: [],
                weather_code: [],
                precipitation_sum: [],
                wind_speed_10m_max: [],
              }}
              loading={initialLoading || (data?.loading ?? true)}
              onRemove={isAdditional ? () => handleCityRemove(city) : undefined}
            />
          );
        })}
      </div>
    </div>
  );
}
