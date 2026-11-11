import type { Metadata } from "next";

import { CommandCenter } from "@/features/dashboard/command-center";

export const metadata: Metadata = {
  title: "Command Center",
  description: "Live national picture of FAA-reported operational events and observed weather at 50 U.S. airports.",
};

export default function DashboardPage() {
  return <CommandCenter />;
}
