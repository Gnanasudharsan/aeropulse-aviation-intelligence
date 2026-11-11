import type { Metadata } from "next";
import { Suspense } from "react";

import { PageContainer } from "@/components/layout/page";
import { PanelSkeleton } from "@/components/data/states";
import { AirportView } from "@/features/airport/airport-view";

export async function generateMetadata({ params }: PageProps<"/airports/[code]">): Promise<Metadata> {
  const { code } = await params;
  return { title: `${code.toUpperCase()} airport intelligence` };
}

function AirportSkeleton() {
  return (
    <PageContainer className="space-y-4 py-10">
      <PanelSkeleton lines={2} />
      <div className="grid gap-4 lg:grid-cols-3">
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
