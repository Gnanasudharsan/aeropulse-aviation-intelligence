import type { Metadata } from "next";

import { RiskView } from "@/features/risk/risk-view";

export const metadata: Metadata = {
  title: "Disruption Risk",
  description: "Transparent, rules-based airport disruption risk indicator with explained components.",
};

export default function RiskPage() {
  return <RiskView />;
}
