"use client";

import { AlertOctagon, Ban, CloudFog, Hourglass, PlaneLanding, Radio, Timer } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { StatusBadge } from "@/components/data/badges";
import { FreshnessStrip } from "@/components/data/freshness-strip";
import { KpiTile } from "@/components/data/kpi";
import { EmptyState, ErrorState, PanelSkeleton, StaleNotice } from "@/components/data/states";
import { PageContainer, PageHeader, Panel } from "@/components/layout/page";
import { AirportMap, type ColorMode } from "@/components/map/airport-map";
import { MapLegend } from "@/components/map/map-legend";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useAirports, useOperationsSummary } from "@/lib/api/hooks";
import type { AirportSummary } from "@/lib/api/schemas";
import { STATUS_ORDER } from "@/lib/domain";

import { AirportQuicklook } from "./airport-quicklook";
import { CategoryBar } from "./category-bar";
import { ChangeFeed } from "./change-feed";

type Filter = "all" | "advisories" | "disrupted" | "lowwx";

const FILTERS: { value: Filter; label: string; test: (a: AirportSummary) => boolean }[] = [
  { value: "all", label: "All", test: () => true },
  { value: "advisories", label: "Any FAA advisory", test: (a) => a.active_advisories > 0 },
  { value: "disrupted", label: "Disruptions", test: (a) => a.status === "critical" || a.status === "warning" },
  { value: "lowwx", label: "IFR / LIFR", test: (a) => !a.weather_is_stale && (a.flight_category === "IFR" || a.flight_category === "LIFR") },
];

export function CommandCenter() {
  const summary = useOperationsSummary();
  const airports = useAirports();
  const [mode, setMode] = useState<ColorMode>("status");
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(null);

  const all = useMemo(() => airports.data?.data ?? [], [airports.data]);
  const visible = useMemo(() => all.filter(FILTERS.find((f) => f.value === filter)!.test), [all, filter]);
  const attention = useMemo(
    () =>
      all
        .filter((a) => a.status !== "normal" && a.status !== "unknown")
        .sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.iata_code.localeCompare(b.iata_code)),
    [all],
  );
  const selectedAirport = all.find((a) => a.iata_code === selected) ?? null;
  const s = summary.data?.data;
  const lowWx = all.filter((a) => !a.weather_is_stale && (a.flight_category === "IFR" || a.flight_category === "LIFR")).length;
  const catCounts = Object.fromEntries((s?.flight_categories ?? []).map((c) => [c.category, c.airports]));
  const unknownWx = s ? s.monitored_airports - (s.flight_categories ?? []).reduce((n, c) => n + c.airports, 0) : 0;
  const stale = s && (s.faa_health !== "healthy" || s.weather_health !== "healthy");

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Live · FAA NAS Status + NOAA AWC"
        title="National Aviation Command Center"
        description="Reported FAA operational events and observed weather across 50 major U.S. airports. Statuses come only from FAA reports and METAR observations — never inferred."
        meta={<FreshnessStrip dataUpdatedAt={summary.dataUpdatedAt || undefined} />}
      />

      {stale && (
        <div className="mb-4">
          <StaleNotice>
            {s.faa_health !== "healthy" && <>FAA NAS Status ingestion is <strong>{s.faa_health}</strong>. </>}
            {s.weather_health !== "healthy" && <>METAR ingestion is <strong>{s.weather_health}</strong>. </>}
            Figures show the last successfully ingested data and may not reflect current conditions.
          </StaleNotice>
        </div>
      )}

      {summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} className="mb-6" />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <KpiTile label="Monitored airports" value={s?.monitored_airports ?? null} icon={PlaneLanding} tone="accent" loading={summary.isPending} footer="Top U.S. commercial airports" />
          <KpiTile
            label="Airports with FAA advisories"
            value={s?.airports_with_active_advisories ?? null}
            icon={Radio}
            tone="neutral"
            loading={summary.isPending}
            footer={s ? `${s.active_partial_closures} partial-closure NOTAMs` : undefined}
            hint="Any active FAA NAS Status event, including partial NOTAM closures"
          />
          <KpiTile label="Ground stops" value={s?.active_ground_stops ?? null} icon={Ban} tone={s?.active_ground_stops ? "crit" : "ok"} loading={summary.isPending} footer="FAA-reported, active now" />
          <KpiTile label="Ground delay programs" value={s?.active_ground_delay_programs ?? null} icon={Hourglass} tone={s?.active_ground_delay_programs ? "crit" : "ok"} loading={summary.isPending} footer="FAA-reported, active now" />
          <KpiTile label="Reported delays" value={s?.active_reported_delays ?? null} icon={Timer} tone={s?.active_reported_delays ? "warn" : "ok"} loading={summary.isPending} footer="Airports with arr/dep delays" />
          <KpiTile label="IFR / LIFR airports" value={airports.data ? lowWx : null} icon={CloudFog} tone={lowWx ? "warn" : "ok"} loading={airports.isPending} footer="From latest METAR (≤ 2 h old)" />
        </div>
      )}

      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-8"
          title="National airport map"
          description="Marker position = airport reference point. Hover or focus a marker for conditions; select to inspect."
          bodyClassName="space-y-3"
          actions={
            <ToggleGroup type="single" size="sm" variant="outline" value={mode} onValueChange={(v) => v && setMode(v as ColorMode)} aria-label="Colour markers by">
              <ToggleGroupItem value="status" className="px-2.5 text-xs">Status</ToggleGroupItem>
              <ToggleGroupItem value="category" className="px-2.5 text-xs">Flight category</ToggleGroupItem>
            </ToggleGroup>
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <ToggleGroup type="single" size="sm" value={filter} onValueChange={(v) => v && setFilter(v as Filter)} aria-label="Filter airports">
              {FILTERS.map((f) => (
                <ToggleGroupItem key={f.value} value={f.value} className="px-2.5 text-xs data-[state=on]:bg-ap-accent-soft data-[state=on]:text-ap-accent">
                  {f.label} <span className="tabular ml-1 text-ap-text-3">{all.filter(f.test).length}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            <MapLegend mode={mode} />
          </div>
          {airports.isError ? (
            <ErrorState error={airports.error} onRetry={() => airports.refetch()} className="h-[420px]" />
          ) : (
            <AirportMap airports={visible} colorMode={mode} selected={selected} onSelect={setSelected} className="h-[420px] sm:h-[520px]" />
          )}
          {airports.data && visible.length === 0 && (
            <p className="text-center text-xs text-ap-text-3">No airports match this filter right now.</p>
          )}
        </Panel>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <Panel title={selectedAirport ? "Selected airport" : "Airports needing attention"} description={selectedAirport ? undefined : "FAA-reported disruptions and IFR/LIFR observations, most severe first."}>
            {selectedAirport ? (
              <AirportQuicklook airport={selectedAirport} onClose={() => setSelected(null)} />
            ) : airports.isPending ? (
              <PanelSkeleton className="border-0 p-0 shadow-none" lines={4} />
            ) : attention.length === 0 ? (
              <EmptyState title="Nothing flagged" icon={<AlertOctagon className="size-6 text-ap-ok" aria-hidden />}>
                No FAA disruptions or IFR/LIFR observations at monitored airports.
              </EmptyState>
            ) : (
              <ul className="-mx-2 max-h-[300px] space-y-0.5 overflow-auto">
                {attention.map((a) => (
                  <li key={a.iata_code}>
                    <button
                      type="button"
                      onClick={() => setSelected(a.iata_code)}
                      className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-white/[0.03]"
                    >
                      <span className="w-10 font-mono text-sm font-semibold">{a.iata_code}</span>
                      <span className="min-w-0 flex-1 truncate text-xs text-ap-text-2">{a.status_reason}</span>
                      <StatusBadge status={a.status} compact />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Flight categories now" description="Latest METAR per airport; observations older than 2 h count as N/A.">
            {s ? <CategoryBar counts={catCounts} unknown={unknownWx} /> : <PanelSkeleton className="border-0 p-0 shadow-none" lines={2} />}
          </Panel>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-12">
        <Panel
          className="lg:col-span-7"
          title="Recent operational changes"
          description={s ? `${s.changes_last_hour} change${s.changes_last_hour === 1 ? "" : "s"} detected in the last hour` : undefined}
          actions={
            <Link href="/events" className="text-xs text-ap-accent hover:underline">
              Event explorer →
            </Link>
          }
        >
          {s ? <ChangeFeed events={s.recent_changes} /> : <PanelSkeleton className="border-0 p-0 shadow-none" lines={5} />}
        </Panel>
        <Panel className="lg:col-span-5" title="Status breakdown" description="How the 50 airports are classified right now (rules in Methodology).">
          {s ? (
            <ul className="space-y-2.5">
              {STATUS_ORDER.map((st) => {
                const n = s.status_counts[st] ?? 0;
                return (
                  <li key={st} className="flex items-center gap-3">
                    <StatusBadge status={st} className="w-44 justify-start" />
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
                      <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${(n / Math.max(s.monitored_airports, 1)) * 100}%`, background: `var(--ap-${{ critical: "crit", warning: "warn", weather: "lifr", normal: "ok", unknown: "unknown" }[st]})` }} />
                    </div>
                    <span className="tabular w-6 text-right text-sm">{n}</span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <PanelSkeleton className="border-0 p-0 shadow-none" lines={5} />
          )}
          <p className="mt-4 text-[11px] leading-relaxed text-ap-text-3">
            <Link href="/methodology#status" className="text-ap-text-2 underline-offset-2 hover:underline">
              Classification rules
            </Link>{" "}
            · Weather alone never produces an FAA-program status.
          </p>
        </Panel>
      </div>
    </PageContainer>
  );
}
