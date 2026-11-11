import type { Metadata } from "next";

import { AirportExplorer } from "@/features/airports/airport-explorer";

export const metadata: Metadata = {
  title: "Airport Explorer",
  description: "Search and filter 50 monitored U.S. airports by FAA-reported status and observed weather.",
};

export default function AirportsPage() {
  return <AirportExplorer />;
}
