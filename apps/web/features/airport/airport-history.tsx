"use client";

import Link from "next/link";
import { useState } from "react";

import { EmptyState, ErrorState, PanelSkeleton } from "@/components/data/states";
import { useAnalytics } from "@/lib/api/hooks";
import { CarrierTable, DelayDrivers, MonthlyTrend, PerfKpis, TemporalPatterns } from "@/features/analytics/performance-views";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

/** Historical BTS performance for one airport — clearly separated from live data. */
export function AirportHistory({ code }: { code: string }) {
  const [direction, setDirection] = useState<"arrival" | "departure">("arrival");
  const q = useAnalytics({ direction }, code);
  const d = q.data?.data;
  return (
    <section className="mt-10 space-y-4" aria-labelledby="history-heading">
      <div className="flex flex-wrap items-end justify-between gap-3 border-t border-ap-line pt-8">
        <div>
          <p className="ap-eyebrow">Historical · BTS On-Time Performance</p>
          <h2 id="history-heading" className="mt-1 text-xl font-semibold">{code} performance history</h2>
          {d?.available && (
            <p className="mt-1 text-xs text-ap-text-3">
              Latest 12 loaded months · compared with all 50 monitored airports · <Link href="/analytics" className="text-ap-accent underline underline-offset-2">network analytics</Link>
            </p>
          )}
        </div>
        <ToggleGroup type="single" size="sm" variant="outline" value={direction} onValueChange={(v) => v && setDirection(v as "arrival" | "departure")} aria-label="Direction">
          <ToggleGroupItem value="arrival" className="px-2.5 text-xs">Arrivals</ToggleGroupItem>
          <ToggleGroupItem value="departure" className="px-2.5 text-xs">Departures</ToggleGroupItem>
        </ToggleGroup>
      </div>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !d ? (
        <PanelSkeleton lines={5} />
      ) : !d.available || !d.totals ? (
        <EmptyState title="No historical data loaded">BTS on-time performance has not been loaded for this environment.</EmptyState>
      ) : (
        <>
          <PerfKpis data={d} />
          <MonthlyTrend data={d} />
          <DelayDrivers data={d} />
          <TemporalPatterns data={d} />
          <CarrierTable data={d} limit={10} />
        </>
      )}
    </section>
  );
}
