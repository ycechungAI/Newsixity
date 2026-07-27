"use client";

import { useState, useEffect, useCallback } from "react";
import type { CityConfig, CityWeatherData } from "@/lib/weather/types";
import {
  addLocation,
  fetchForecast,
  fetchLocations,
  removeLocation,
  type SavedLocation,
} from "@/lib/weather/api";
import { DEFAULT_CITIES, LOCAL_CITY } from "@/lib/weather/constants";
import CurrentWeatherCard from "./CurrentWeatherCard";
import ForecastCard from "./ForecastCard";
import CitySearch from "./CitySearch";
import WeatherTimeline from "./WeatherTimeline";

function cityKey(city: CityConfig): string {
  return `${city.latitude},${city.longitude}`;
}

export default function WeatherDashboard() {
  const [cityForecasts, setCityForecasts] = useState<Map<string, CityWeatherData>>(new Map());
  const [additionalCities, setAdditionalCities] = useState<CityConfig[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  /** Saved cities from the DB — these survive a reload. */
  const [saved, setSaved] = useState<SavedLocation[]>([]);

  const reloadSaved = useCallback(async () => {
    try {
      setSaved(await fetchLocations());
    } catch {
      setSaved([]);  // Timeline hides itself when this is empty.
    }
  }, []);

  // Restore previously-saved cities, then fetch their forecasts alongside the
  // defaults. Without this, added cities vanished on every reload.
  useEffect(() => {
    (async () => {
      // Register the built-in cities so they get a row (and therefore
      // history) too — otherwise only cities the user explicitly added
      // would ever appear in the timeline. addLocation is idempotent on
      // (latitude, longitude), so this is safe on every mount.
      await Promise.allSettled(
        DEFAULT_CITIES.map((c) => addLocation(c.name, c.latitude, c.longitude, c.country))
      );

      const locations = await fetchLocations().catch(() => [] as SavedLocation[]);
      setSaved(locations);
      const restored = locations.map((l) => ({
        name: l.name,
        country: l.country ?? "",
        latitude: l.latitude,
        longitude: l.longitude,
      })) as CityConfig[];

      // Defaults are rendered separately; don't list them twice.
      const extra = restored.filter(
        (c) => !DEFAULT_CITIES.some((d) => cityKey(d) === cityKey(c))
      );
      setAdditionalCities(extra);

      const results = await Promise.allSettled(
        extra.map((c) => fetchForecast(c.latitude, c.longitude))
      );
      setCityForecasts((prev) => {
        const next = new Map(prev);
        results.forEach((result, i) => {
          const city = extra[i];
          next.set(cityKey(city), result.status === "fulfilled"
            ? { city, forecast: result.value, loading: false, error: null }
            : { city, forecast: null, loading: false, error: "Failed to load weather" });
        });
        return next;
      });
    })();
  }, []);

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
            dataMap.set(key, { city, forecast: result.value, loading: false, error: null });
          } else {
            dataMap.set(key, { city, forecast: null, loading: false, error: result.reason?.message ?? "Failed to load" });
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

  const handleCitySelect = useCallback(async (city: CityConfig) => {
    const key = cityKey(city);
    if (cityForecasts.has(key)) return;
    setAdditionalCities((prev) => [...prev, city]);
    setCityForecasts((prev) => {
      const next = new Map(prev);
      next.set(key, { city, forecast: null, loading: true, error: null });
      return next;
    });
    try {
      // Save first: the forecast endpoint only records history for cities
      // that already exist in the DB, so ordering matters here.
      await addLocation(city.name, city.latitude, city.longitude, city.country).catch(() => {});
      reloadSaved();

      const forecast = await fetchForecast(city.latitude, city.longitude);
      setCityForecasts((prev) => {
        const next = new Map(prev);
        next.set(key, { city, forecast, loading: false, error: null });
        return next;
      });
    } catch {
      setCityForecasts((prev) => {
        const next = new Map(prev);
        next.set(key, { city, forecast: null, loading: false, error: "Failed to load weather" });
        return next;
      });
    }
  }, [cityForecasts, reloadSaved]);

  const handleCityRemove = useCallback((city: CityConfig) => {
    const key = cityKey(city);
    setAdditionalCities((prev) => prev.filter((c) => cityKey(c) !== key));
    setCityForecasts((prev) => {
      const next = new Map(prev);
      next.delete(key);
      return next;
    });

    // Drop it server-side too, or it would reappear on the next reload.
    // Matched on coordinates, since that's the DB's unique key.
    setSaved((prev) => {
      const match = prev.find(
        (l) =>
          Math.abs(l.latitude - city.latitude) < 0.01 &&
          Math.abs(l.longitude - city.longitude) < 0.01
      );
      if (match) removeLocation(match.id).catch(() => {});
      return prev.filter((l) => l.id !== match?.id);
    });
  }, []);

  const localData = cityForecasts.get(cityKey(LOCAL_CITY));
  const allCities = [...DEFAULT_CITIES, ...additionalCities];

  return (
    <div className="wx-page">
      <div className="wx-header">
        <div>
          <div className="page-title">Weather</div>
          <div className="page-sub">Current conditions &amp; 7-day forecasts</div>
        </div>
        <div className="wx-search-wrap">
          <CitySearch onCitySelect={handleCitySelect} />
        </div>
      </div>

      {error && (
        <div style={{ color: "var(--danger, #e53e3e)", marginBottom: 8, fontSize: 11 }}>{error}</div>
      )}

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

      <WeatherTimeline locations={saved} />

      <div className="wx-grid">
        {allCities.map((city) => {
          const key = cityKey(city);
          const data = cityForecasts.get(key);
          const isAdditional = additionalCities.some((c) => cityKey(c) === key);

          if (data?.error) {
            return (
              <div key={key} className="wx-card">
                <div className="wx-card-head">
                  <span>{city.name}, {city.country}</span>
                  {isAdditional && (
                    <button className="wx-remove-btn" onClick={() => handleCityRemove(city)} title="Remove">✕</button>
                  )}
                </div>
                <div style={{ color: "#e53e3e", fontSize: 11 }}>{data.error}</div>
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
