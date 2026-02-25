import type { Metadata } from "next";
import WeatherDashboard from "@/components/weather/WeatherDashboard";

export const metadata: Metadata = {
  title: "Weather - Newsixity",
  description: "Weather dashboard with current conditions and 7-day forecasts",
};

export default function WeatherPage() {
  return <WeatherDashboard />;
}
