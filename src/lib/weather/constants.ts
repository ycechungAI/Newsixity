import type { CityConfig } from "./types";

export const DEFAULT_CITIES: CityConfig[] = [
  { name: "Markham", country: "Canada", latitude: 43.8561, longitude: -79.337 },
  { name: "Vancouver", country: "Canada", latitude: 49.2827, longitude: -123.1207 },
  { name: "Hong Kong", country: "China", latitude: 22.3193, longitude: 114.1694 },
  { name: "Tokyo", country: "Japan", latitude: 35.6762, longitude: 139.6503 },
];

// Markham is the "local" city shown in the hero card
export const LOCAL_CITY = DEFAULT_CITIES[0];
