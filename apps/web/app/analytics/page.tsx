import type { Metadata } from "next";

import { AnalyticsView } from "@/features/analytics/analytics-view";

export const metadata: Metadata = {
  title: "Performance Analytics",
  description: "Historical BTS on-time performance, delay drivers and seasonal patterns for 50 U.S. airports, with Power BI integration.",
};

export default function AnalyticsPage() {
  return <AnalyticsView />;
}
