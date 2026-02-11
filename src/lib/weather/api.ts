import type { ForecastResponse, GeocodingResponse } from "./types";

const FORECAST_BASE = "https://api.open-meteo.com/v1/forecast";
const GEOCODING_BASE = "https://geocoding-api.open-meteo.com/v1/search";

export async function fetchForecast(
  latitude: number,
  longitude: number
): Promise<ForecastResponse> {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    daily:
      "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum,wind_speed_10m_max",
    current:
      "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
    timezone: "auto",
    forecast_days: "7",
  });

  const res = await fetch(`${FORECAST_BASE}?${params}`);
  if (!res.ok) throw new Error(`Forecast API error: ${res.status}`);
  return res.json();
}

export async function searchCities(
  query: string
): Promise<GeocodingResponse> {
  const params = new URLSearchParams({
    name: query,
    count: "5",
    language: "en",
  });

  const res = await fetch(`${GEOCODING_BASE}?${params}`);
  if (!res.ok) throw new Error(`Geocoding API error: ${res.status}`);
  return res.json();
}
