import type { Metadata } from "next";

import { WeatherIntelligence } from "@/features/weather/weather-intelligence";

export const metadata: Metadata = {
  title: "Weather Impact",
  description: "Observed METAR conditions, flight categories, TAF forecasts and their overlap with FAA advisories.",
};

export default function WeatherPage() {
  return <WeatherIntelligence />;
}
