// Geocoding API response
export interface GeocodingResult {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  country: string;
  country_code: string;
  admin1?: string; // Province/State
}

export interface GeocodingResponse {
  results?: GeocodingResult[];
}

// Forecast API current conditions
export interface CurrentWeather {
  temperature_2m: number;
  relative_humidity_2m: number;
  apparent_temperature: number;
  weather_code: number;
  wind_speed_10m: number;
}

// Forecast API daily data
export interface DailyForecast {
  time: string[];
  temperature_2m_max: number[];
  temperature_2m_min: number[];
  weather_code: number[];
  precipitation_sum: number[];
  wind_speed_10m_max: number[];
}

// Full forecast API response
export interface ForecastResponse {
  latitude: number;
  longitude: number;
  timezone: string;
  current: CurrentWeather;
  daily: DailyForecast;
}

// Internal city configuration
export interface CityConfig {
  name: string;
  country: string;
  latitude: number;
  longitude: number;
}

// City weather data with loading/error state
export interface CityWeatherData {
  city: CityConfig;
  forecast: ForecastResponse | null;
  loading: boolean;
  error: string | null;
}
