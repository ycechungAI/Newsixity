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
      <div className="wx-current wx-skeleton">
        <div className="wx-current-body">
          <div style={{ fontSize: 36, opacity: 0.2 }}>—</div>
          <div className="wx-temp-block">
            <div className="wx-temp" style={{ opacity: 0.2 }}>--°C</div>
            <div style={{ opacity: 0.2 }}>Loading…</div>
          </div>
        </div>
        <div className="wx-stats">
          {["Feels Like", "Humidity", "Wind", "High / Low"].map(l => (
            <div key={l} className="wx-stat">
              <div style={{ opacity: 0.2 }}>{l}</div>
              <div style={{ opacity: 0.2 }}>--</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const weatherInfo = getWeatherInfo(current.weather_code);
  const todayHigh = daily.temperature_2m_max[0];
  const todayLow = daily.temperature_2m_min[0];

  return (
    <div className="wx-current">
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{cityName}, {country}</div>
      <div className="wx-current-body">
        <span className="wx-emoji" role="img" aria-label={weatherInfo.label}>{weatherInfo.emoji}</span>
        <div className="wx-temp-block">
          <div className="wx-temp">{Math.round(current.temperature_2m)}°C</div>
          <div style={{ color: "var(--muted)", fontSize: 11 }}>{weatherInfo.label}</div>
        </div>
      </div>
      <div className="wx-stats">
        <div className="wx-stat">
          <div>Feels Like</div>
          <strong>{Math.round(current.apparent_temperature)}°C</strong>
        </div>
        <div className="wx-stat">
          <div>Humidity</div>
          <strong>{current.relative_humidity_2m}%</strong>
        </div>
        <div className="wx-stat">
          <div>Wind</div>
          <strong>{Math.round(current.wind_speed_10m)} km/h</strong>
        </div>
        <div className="wx-stat">
          <div>High / Low</div>
          <strong>{Math.round(todayHigh)}° / {Math.round(todayLow)}°</strong>
        </div>
      </div>
    </div>
  );
}
