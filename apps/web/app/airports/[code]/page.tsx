import type { Metadata } from "next";
import { Suspense } from "react";

import { PageContainer } from "@/components/layout/page";
import { PanelSkeleton } from "@/components/data/states";
import { AirportView } from "@/features/airport/airport-view";
import { MONITORED_AIRPORTS } from "@/lib/airports";

export function generateStaticParams() {
  return MONITORED_AIRPORTS.map((code) => ({ code }));
}

export async function generateMetadata({ params }: PageProps<"/airports/[code]">): Promise<Metadata> {
  const { code } = await params;
  const c = code.toUpperCase();
  return {
    title: `${c} airport intelligence`,
    description: `Live FAA advisories, observed METAR weather, TAF forecast and historical on-time performance for ${c}.`,
  };
}

function AirportSkeleton() {
  return (
    <PageContainer className="space-y-4 py-10">
      <PanelSkeleton lines={2} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <PanelSkeleton lines={6} className="lg:col-span-2" />
        <PanelSkeleton lines={6} />
      </div>
    </PageContainer>
  );
}

export default function AirportPage({ params }: PageProps<"/airports/[code]">) {
  return (
    <Suspense fallback={<AirportSkeleton />}>
      {params.then(({ code }) => (
        <AirportView code={code.toUpperCase()} />
      ))}
    </Suspense>
  );
}
