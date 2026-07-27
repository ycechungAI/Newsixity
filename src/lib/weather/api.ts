import type { ForecastResponse, GeocodingResponse } from "./types";

/**
 * Weather data now comes from the backend rather than being fetched from
 * Open-Meteo directly in the browser.
 *
 * The direct calls did work — Open-Meteo sends permissive CORS headers — but
 * they meant results could never be persisted (so no history, and every
 * mount refired the requests), and they left the feature depending on a
 * third party's CORS policy. That exact assumption is what silently broke
 * the YouTube playlist feature, which failed closed and rendered nothing.
 *
 * The backend proxies and caches these, and records observations for saved
 * cities, which is what makes the timeline possible.
 */

export async function fetchForecast(
  latitude: number,
  longitude: number,
  days = 7
): Promise<ForecastResponse> {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    days: String(days),
  });

  const res = await fetch(`/api/weather/forecast?${params}`);
  if (!res.ok) throw new Error(`Forecast API error: ${res.status}`);
  return res.json();
}

export async function searchCities(query: string): Promise<GeocodingResponse> {
  const res = await fetch(`/api/weather/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Geocoding API error: ${res.status}`);
  return res.json();
}

export interface SavedLocation {
  id: number;
  name: string;
  country: string | null;
  latitude: number;
  longitude: number;
  sortOrder: number;
}

export interface HistoryDay {
  date: string;
  tempMax: number | null;
  tempMin: number | null;
  precipitation: number | null;
  weatherCode: number | null;
  windSpeedMax: number | null;
}

/** Cities the user saved. Persisted server-side, so they survive a reload. */
export async function fetchLocations(): Promise<SavedLocation[]> {
  const res = await fetch("/api/weather/locations");
  if (!res.ok) throw new Error(`Locations error: ${res.status}`);
  return (await res.json()).locations ?? [];
}

export async function addLocation(
  name: string,
  latitude: number,
  longitude: number,
  country?: string | null
): Promise<number> {
  const params = new URLSearchParams({
    name,
    latitude: String(latitude),
    longitude: String(longitude),
  });
  if (country) params.set("country", country);

  const res = await fetch(`/api/weather/locations?${params}`, { method: "POST" });
  if (!res.ok) throw new Error(`Add location error: ${res.status}`);
  return (await res.json()).id;
}

export async function removeLocation(id: number): Promise<void> {
  const res = await fetch(`/api/weather/locations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Remove location error: ${res.status}`);
}

export async function fetchHistory(locationId: number, days = 30): Promise<HistoryDay[]> {
  const res = await fetch(`/api/weather/history?location_id=${locationId}&days=${days}`);
  if (!res.ok) throw new Error(`History error: ${res.status}`);
  return (await res.json()).days ?? [];
}

/**
 * Populate history from Open-Meteo's archive. Without this the timeline is
 * empty until the app has run for weeks; the archive is free and goes back
 * decades, so history is useful immediately.
 */
export async function backfillHistory(locationId: number, days = 365): Promise<number> {
  const res = await fetch(
    `/api/weather/backfill?location_id=${locationId}&days=${days}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Backfill error: ${res.status}`);
  return (await res.json()).days ?? 0;
}
