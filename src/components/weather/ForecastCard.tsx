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

function getDayName(dateString: string): string {
  const date = new Date(dateString + "T00:00:00");
  return date.toLocaleDateString("en-US", { weekday: "short" });
}

export default function ForecastCard({ cityName, country, daily, loading, onRemove }: ForecastCardProps) {
  if (loading) {
    return (
      <div className="wx-card wx-skeleton">
        <div className="wx-card-head">
          <span style={{ opacity: 0.3 }}>Loading…</span>
        </div>
        <div className="wx-days">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="wx-day">
              <div className="wx-day-name" style={{ opacity: 0.2 }}>---</div>
              <div className="wx-day-emoji" style={{ opacity: 0.2 }}>·</div>
              <div className="wx-day-hi" style={{ opacity: 0.2 }}>--°</div>
              <div className="wx-day-lo" style={{ opacity: 0.2 }}>--°</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="wx-card">
      <div className="wx-card-head">
        <span>{cityName}, {country}</span>
        {onRemove && (
          <button className="wx-remove-btn" onClick={onRemove} title="Remove city">✕</button>
        )}
      </div>
      <div className="wx-days">
        {daily.time.map((date, i) => {
          const info = getWeatherInfo(daily.weather_code[i]);
          return (
            <div key={date} className="wx-day">
              <div className="wx-day-name">{i === 0 ? "Today" : getDayName(date)}</div>
              <div className="wx-day-emoji" role="img" aria-label={info.label}>{info.emoji}</div>
              <div className="wx-day-hi">{Math.round(daily.temperature_2m_max[i])}°</div>
              <div className="wx-day-lo">{Math.round(daily.temperature_2m_min[i])}°</div>
              {daily.precipitation_sum[i] > 0 && (
                <div className="wx-day-rain">{daily.precipitation_sum[i].toFixed(1)}mm</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
