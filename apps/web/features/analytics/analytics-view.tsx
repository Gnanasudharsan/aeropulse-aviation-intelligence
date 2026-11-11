"use client";

import { useState } from "react";

import { EmptyState, ErrorState, PanelSkeleton } from "@/components/data/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { useAnalytics } from "@/lib/api/hooks";

import {
  AirportMonthHeatmap,
  AirportRanking,
  CarrierTable,
  DelayDrivers,
  MonthlyTrend,
  PerfKpis,
  type Period,
  PeriodControls,
  periodRange,
  TemporalPatterns,
} from "./performance-views";
import { PowerBiPanel } from "./powerbi-panel";

const fmtMonth = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" }) : "—";

export function AnalyticsView() {
  const [direction, setDirection] = useState<"arrival" | "departure">("arrival");
  const [period, setPeriod] = useState<Period>("12m");
  // Coverage comes from an unfiltered request; the period is resolved against it.
  const base = useAnalytics({ direction });
  const cov = base.data?.data.coverage;
  const range = periodRange(period, cov?.first_month ?? null, cov?.last_month ?? null);
  const q = useAnalytics({ direction, ...range });
  const d = q.data?.data ?? base.data?.data;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Historical analytics · BTS On-Time Performance"
        title="Airport performance analytics"
        description="Historical on-time, delay and cancellation performance for the 50 monitored airports, from U.S. DOT Bureau of Transportation Statistics data. Kept separate from live operations."
        meta={
          d?.available ? (
            <p className="text-xs text-ap-text-3">
              Showing {fmtMonth(d.coverage.selected_start)} – {fmtMonth(d.coverage.selected_end)} · {d.coverage.months_loaded} months loaded ({fmtMonth(d.coverage.first_month)} – {fmtMonth(d.coverage.last_month)}) · {d.coverage.lag_note}
            </p>
          ) : null
        }
        actions={d?.available ? <PeriodControls data={d} period={period} onPeriod={setPeriod} direction={direction} onDirection={setDirection} /> : null}
      />
      <div className="space-y-4">
        <PowerBiPanel />
        {q.isError || base.isError ? (
          <ErrorState error={q.error ?? base.error} onRetry={() => { void base.refetch(); void q.refetch(); }} />
        ) : !d ? (
          <PanelSkeleton lines={8} />
        ) : !d.available || !d.totals ? (
          <EmptyState title="Historical data has not been loaded">
            Run the BTS pipeline (<code className="font-mono text-xs">pipelines/historical/bts_pipeline.py</code>) to load on-time performance data.
          </EmptyState>
        ) : (
          <>
            <PerfKpis data={d} />
            <MonthlyTrend data={d} />
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
              <AirportRanking data={d} />
              <AirportMonthHeatmap data={d} />
            </div>
            <DelayDrivers data={d} />
            <TemporalPatterns data={d} />
            <CarrierTable data={d} />
          </>
        )}
      </div>
    </PageContainer>
  );
}
