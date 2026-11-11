"use client";

import { ArrowDownUp, Search } from "lucide-react";
import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";

import { CategoryBadge, StatusBadge } from "@/components/data/badges";
import { FreshnessStrip } from "@/components/data/freshness-strip";
import { EmptyState, ErrorState, PanelSkeleton } from "@/components/data/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useNow } from "@/hooks/use-now";
import { useAirports } from "@/lib/api/hooks";
import type { AirportStatus, AirportSummary } from "@/lib/api/schemas";
import { FLIGHT_CATEGORIES, STATUS_META, STATUS_ORDER } from "@/lib/domain";
import { num, relativeTime } from "@/lib/format";

type SortKey = "severity" | "code" | "visibility" | "wind" | "advisories";

const SORTS: Record<SortKey, { label: string; cmp: (a: AirportSummary, b: AirportSummary) => number }> = {
  severity: {
    label: "Severity",
    cmp: (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.iata_code.localeCompare(b.iata_code),
  },
  code: { label: "Airport code", cmp: (a, b) => a.iata_code.localeCompare(b.iata_code) },
  visibility: { label: "Lowest visibility", cmp: (a, b) => (a.visibility_sm ?? 99) - (b.visibility_sm ?? 99) },
  wind: {
    label: "Strongest wind",
    cmp: (a, b) => Math.max(b.wind_speed_kt ?? 0, b.wind_gust_kt ?? 0) - Math.max(a.wind_speed_kt ?? 0, a.wind_gust_kt ?? 0),
  },
  advisories: { label: "Most advisories", cmp: (a, b) => b.active_advisories - a.active_advisories },
};

export function AirportExplorer() {
  const now = useNow();
  const { data, isPending, isError, error, refetch, dataUpdatedAt } = useAirports();
  const [query, setQuery] = useState("");
  const q = useDeferredValue(query.trim().toLowerCase());
  const [status, setStatus] = useState<AirportStatus | "all">("all");
  const [category, setCategory] = useState<string>("all");
  const [sort, setSort] = useState<SortKey>("severity");

  const rows = useMemo(() => {
    const list = (data?.data ?? []).filter((a) => {
      if (q && !`${a.iata_code} ${a.icao_code} ${a.name} ${a.city} ${a.state}`.toLowerCase().includes(q)) return false;
      if (status !== "all" && a.status !== status) return false;
      if (category !== "all" && (a.weather_is_stale || a.flight_category !== category)) return false;
      return true;
    });
    return list.sort(SORTS[sort].cmp);
  }, [data, q, status, category, sort]);

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Airport Explorer"
        title="50 monitored U.S. airports"
        description="Search by code, name, city or state. Filter by FAA-derived status or observed flight category; select an airport for full intelligence."
        meta={<FreshnessStrip dataUpdatedAt={dataUpdatedAt || undefined} />}
      />
      <div className="ap-panel mb-4 flex flex-col gap-3 p-3 lg:flex-row lg:items-center">
        <label className="relative flex-1">
          <span className="sr-only">Search airports</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ap-text-3" aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search JFK, KORD, Denver, TX…" className="h-9 bg-ap-bg/60 pl-9" />
        </label>
        <ToggleGroup type="single" size="sm" value={status} onValueChange={(v) => v && setStatus(v as AirportStatus | "all")} aria-label="Filter by status" className="flex-wrap">
          <ToggleGroupItem value="all" className="px-2.5 text-xs">All</ToggleGroupItem>
          {STATUS_ORDER.map((s) => (
            <ToggleGroupItem key={s} value={s} className="px-2.5 text-xs" title={STATUS_META[s].description}>
              <span className="mr-1 size-1.5 rounded-full" style={{ background: STATUS_META[s].color }} aria-hidden />
              {STATUS_META[s].label.split(" ")[0]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="flex gap-2">
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger size="sm" className="w-[130px]" aria-label="Flight category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {FLIGHT_CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
            <SelectTrigger size="sm" className="w-[170px]" aria-label="Sort by">
              <ArrowDownUp className="size-3.5" aria-hidden />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(SORTS).map(([k, v]) => (
                <SelectItem key={k} value={k}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : isPending ? (
        <PanelSkeleton lines={8} />
      ) : rows.length === 0 ? (
        <EmptyState title="No airports match">Try a different search term or clear the filters.</EmptyState>
      ) : (
        <>
          <p className="mb-2 text-xs text-ap-text-3" aria-live="polite">
            Showing {rows.length} of {data?.data.length} airports
          </p>
          {/* Desktop table */}
          <div className="ap-panel hidden overflow-hidden md:block">
            <table className="w-full text-sm">
              <caption className="sr-only">Monitored airports with current status and latest observed weather</caption>
              <thead className="bg-ap-surface-2/60 text-left text-xs text-ap-text-3">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Airport</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Category</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Visibility</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Ceiling</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Wind</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Temp</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">FAA adv.</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">METAR</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {rows.map((a) => (
                  <tr key={a.iata_code} className="group border-t border-ap-line transition-colors hover:bg-white/[0.025]">
                    <td className="px-4 py-2.5">
                      <Link href={`/airports/${a.iata_code}`} className="flex items-center gap-3 rounded-sm">
                        <span className="w-10 font-mono font-semibold text-ap-text group-hover:text-ap-accent">{a.iata_code}</span>
                        <span className="min-w-0">
                          <span className="block max-w-[280px] truncate text-ap-text-2">{a.name}</span>
                          <span className="block text-xs text-ap-text-3">
                            {a.city}, {a.state}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td className="px-3 py-2.5"><StatusBadge status={a.status} compact /></td>
                    <td className="px-3 py-2.5"><CategoryBadge category={a.weather_is_stale ? null : a.flight_category} /></td>
                    <td className="px-3 py-2.5 text-right">{num(a.visibility_sm, a.visibility_sm !== null && a.visibility_sm % 1 ? 2 : 0, " SM")}</td>
                    <td className="px-3 py-2.5 text-right">{a.ceiling_ft === null ? <span className="text-ap-text-3">none</span> : num(a.ceiling_ft, 0, " ft")}</td>
                    <td className="px-3 py-2.5 text-right">{a.wind_speed_kt === null ? "—" : `${a.wind_speed_kt}${a.wind_gust_kt ? `G${a.wind_gust_kt}` : ""} kt`}</td>
                    <td className="px-3 py-2.5 text-right">{num(a.temperature_c, 0, "°C")}</td>
                    <td className="px-3 py-2.5 text-right">{a.active_advisories || <span className="text-ap-text-3">0</span>}</td>
                    <td className={`px-4 py-2.5 text-right text-xs ${a.weather_is_stale ? "text-ap-warn" : "text-ap-text-3"}`}>
                      {relativeTime(a.weather_observed_at, now)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Mobile cards */}
          <ul className="grid gap-2 md:hidden">
            {rows.map((a) => (
              <li key={a.iata_code}>
                <Link href={`/airports/${a.iata_code}`} className="ap-panel flex items-center gap-3 p-3">
                  <span className="w-12 font-mono text-lg font-semibold">{a.iata_code}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-ap-text-2">{a.city}, {a.state}</span>
                    <span className="mt-1 flex flex-wrap gap-1">
                      <StatusBadge status={a.status} compact />
                      <CategoryBadge category={a.weather_is_stale ? null : a.flight_category} />
                    </span>
                  </span>
                  <span className="tabular text-right text-xs text-ap-text-3">
                    {num(a.visibility_sm, 0, " SM")}
                    <br />
                    {a.wind_speed_kt ?? "—"} kt
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </PageContainer>
  );
}
