import type { Metadata } from "next";
import { Suspense } from "react";

import { PanelSkeleton } from "@/components/data/states";
import { PageContainer } from "@/components/layout/page";
import { EventExplorer } from "@/features/events/event-explorer";

export const metadata: Metadata = {
  title: "Event Explorer",
  description: "Search, filter and export the lifecycle of FAA NAS Status advisories observed by AeroPulse.",
};

export default function EventsPage() {
  return (
    <Suspense
      fallback={
        <PageContainer className="py-10">
          <PanelSkeleton lines={8} />
        </PageContainer>
      }
    >
      <EventExplorer />
    </Suspense>
  );
}
