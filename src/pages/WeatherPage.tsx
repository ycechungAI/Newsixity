import { useDocumentTitle } from "@/lib/utils/useDocumentTitle";
import WeatherDashboard from "@/components/weather/WeatherDashboard";

export default function WeatherPage() {
  useDocumentTitle("Weather - Newsixity");
  return <WeatherDashboard />;
}
