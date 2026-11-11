"use client";

import type { EChartsOption } from "echarts";
import { Info, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { axisStyle, EChart } from "@/components/charts/echart";
import { CategoryBadge, RiskBadge } from "@/components/data/badges";
import { FreshnessStrip } from "@/components/data/freshness-strip";
import { EmptyState, ErrorState, PanelSkeleton, StaleNotice } from "@/components/data/states";
import { PageContainer, PageHeader, Panel } from "@/components/layout/page";
import { AirportMap } from "@/components/map/airport-map";
import { MapLegend } from "@/components/map/map-legend";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useWeatherOverview, useWeatherTrends } from "@/lib/api/hooks";
import type { AirportSummary, WeatherTrendSeries } from "@/lib/api/schemas";
import { CATEGORY_HEX, CATEGORY_META, FLIGHT_CATEGORIES, HEX, RISK_META } from "@/lib/domain";
import { formatUtc, num } from "@/lib/format";

type Metric = "visibility" | "wind" | "temperature";
type Condition = "all" | "lowvis" | "windy" | "precip" | "ts";

const CONDITIONS: Record<Condition, { label: string; test: (a: AirportSummary) => boolean }> = {
  all: { label: "All", test: () => true },
  lowvis: { label: "Visibility < 3 SM", test: (a) => a.visibility_sm !== null && a.visibility_sm < 3 },
  windy: { label: "Wind/gust ≥ 20 kt", test: (a) => Math.max(a.wind_speed_kt ?? 0, a.wind_gust_kt ?? 0) >= 20 },
  precip: { label: "Precipitation", test: (a) => /RA|SN|DZ|PL|GR|GS|UP/.test(a.wx_string ?? "") },
  ts: { label: "Thunderstorms", test: (a) => (a.wx_string ?? "").includes("TS") },
};

const METRIC: Record<Metric, { label: string; unit: string; value: (a: AirportSummary) => number | null; hourly: (h: WeatherTrendSeries["hourly"][number]) => number | null }> = {
  visibility: { label: "Visibility", unit: "SM", value: (a) => a.visibility_sm, hourly: (h) => h.min_visibility_sm },
  wind: { label: "Wind (max of sustained/gust)", unit: "kt", value: (a) => (a.wind_speed_kt === null ? null : Math.max(a.wind_speed_kt, a.wind_gust_kt ?? 0)), hourly: (h) => (h.max_wind_speed_kt === null ? null : Math.max(h.max_wind_speed_kt, h.max_wind_gust_kt ?? 0)) },
  temperature: { label: "Temperature", unit: "°C", value: (a) => a.temperature_c, hourly: (h) => h.avg_temperature_c },
};

const DEFAULT_TREND = ["SFO", "ORD", "JFK", "DEN"];

export function WeatherIntelligence() {
  const router = useRouter();
  const overview = useWeatherOverview();
  const [metric, setMetric] = useState<Metric>("visibility");
  const [condition, setCondition] = useState<Condition>("all");
  const [trendAirports, setTrendAirports] = useState<string[]>(DEFAULT_TREND);
  const [hours, setHours] = useState(48);
  const trends = useWeatherTrends(trendAirports, hours);

  const o = overview.data?.data;
  const current = useMemo(() => (o?.airports ?? []).filter((a) => !a.weather_is_stale && a.weather_observed_at), [o]);
  const filtered = useMemo(() => current.filter(CONDITIONS[condition].test), [current, condition]);

  const comparison = useMemo(() => {
    const m = METRIC[metric];
    return [...filtered]
      .filter((a) => m.value(a) !== null)
      .sort((a, b) => (metric === "visibility" ? m.value(a)! - m.value(b)! : m.value(b)! - m.value(a)!))
      .slice(0, 20);
  }, [filtered, metric]);

  const compareOption: EChartsOption = {
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "value", name: METRIC[metric].unit, ...axisStyle },
    yAxis: { type: "category", inverse: true, data: comparison.map((a) => a.iata_code), ...axisStyle, axisLabel: { color: HEX.text2, fontFamily: "var(--font-geist-mono)", fontSize: 11 } },
    series: [
      {
        type: "bar",
        barMaxWidth: 12,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", color: HEX.text2, fontSize: 10, formatter: (p: { value: unknown }) => `${p.value}` },
        data: comparison.map((a) => ({
          value: METRIC[metric].value(a),
          itemStyle: { color: a.flight_category ? CATEGORY_HEX[a.flight_category] : HEX.unknown },
        })),
      },
    ],
  };

  const trendSeries = trends.data?.data ?? [];
  const trendOption: EChartsOption = {
    xAxis: { type: "time", ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "value", name: METRIC[metric].unit, scale: metric === "temperature", min: metric === "temperature" ? undefined : 0, ...axisStyle },
    legend: { show: true, top: 0, left: 0 },
    series: trendSeries.map((s) => ({
      name: s.airport,
      type: "line",
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 2, color: HEX.series[trendAirports.indexOf(s.airport) % HEX.series.length] },
      itemStyle: { color: HEX.series[trendAirports.indexOf(s.airport) % HEX.series.length] },
      endLabel: { show: true, formatter: "{a}", color: HEX.text2, fontSize: 10 },
      data: s.hourly.map((h) => [h.hour_utc, METRIC[metric].hourly(h)]),
    })),
    grid: { left: 8, right: 44, top: 32, bottom: 8, containLabel: true },
  };

  const allCodes = (o?.airports ?? []).map((a) => a.iata_code).sort();
  const catCounts = Object.fromEntries((o?.flight_categories ?? []).map((c) => [c.category, c.airports]));

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Weather Impact Intelligence · NOAA AWC"
        title="Observed weather across the network"
        description="Latest METAR observations, terminal forecasts and their overlap with FAA-reported events. Observations and forecasts are always shown separately."
        meta={<FreshnessStrip dataUpdatedAt={overview.dataUpdatedAt || undefined} />}
      />
      {o && o.weather_health !== "healthy" && (
        <div className="mb-4">
          <StaleNotice>METAR ingestion is {o.weather_health}. Values reflect the last successful ingestion.</StaleNotice>
        </div>
      )}
      {overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
      ) : !o ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3"><PanelSkeleton lines={6} className="lg:col-span-2" /><PanelSkeleton lines={6} /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <Panel className="lg:col-span-7" title="Flight categories (observed)" description="Colour = METAR flight category. Airports with no observation in 2 h are grey." bodyClassName="space-y-3">
              <MapLegend mode="category" counts={{ ...catCounts, none: o.airports.length - current.length }} />
              <AirportMap airports={o.airports} colorMode="category" className="h-[380px]" onSelect={(code) => router.push(`/airports/${code}`)} />
            </Panel>
            <div className="flex flex-col gap-4 lg:col-span-5">
              <Panel title="What the categories mean">
                <ul className="space-y-2 text-sm">
                  {FLIGHT_CATEGORIES.map((c) => (
                    <li key={c} className="flex items-start gap-3">
                      <CategoryBadge category={c} className="w-14 justify-center" />
                      <span className="text-ap-text-2">{CATEGORY_META[c].description}</span>
                      <span className="tabular ml-auto font-semibold">{catCounts[c] ?? 0}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 flex gap-2 text-xs leading-relaxed text-ap-text-3">
                  <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  IFR/LIFR means instrument procedures are required; airports routinely operate in these conditions, often at reduced arrival rates. It does not by itself mean delays or a ground stop.
                </p>
              </Panel>
              <Panel title="Observed weather risk" description="Rule-based tiers from the latest METAR (see Methodology).">
                <div className="grid grid-cols-5 gap-2 text-center">
                  {(["low", "elevated", "high", "severe", "unknown"] as const).map((r) => (
                    <div key={r} className="rounded-lg border border-ap-line p-2">
                      <p className="text-[10px]" style={{ color: RISK_META[r].color }}>{RISK_META[r].label}</p>
                      <p className="tabular text-lg font-semibold">{o.risk_counts[r] ?? 0}</p>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            {(
              [
                ["Lowest visibility", o.lowest_visibility, "SM"],
                ["Strongest wind / gust", o.strongest_wind, "kt"],
                ["Lowest ceiling", o.lowest_ceiling, "ft"],
              ] as const
            ).map(([title, list, unit]) => (
              <Panel key={title} title={title}>
                {list.length === 0 ? (
                  <p className="text-sm text-ap-text-3">No current reports.</p>
                ) : (
                  <ol className="space-y-1.5">
                    {list.map((e, i) => (
                      <li key={e.airport} className="flex items-center gap-3 text-sm">
                        <span className="w-4 text-xs text-ap-text-3">{i + 1}</span>
                        <Link href={`/airports/${e.airport}`} className="font-mono font-semibold hover:text-ap-accent">{e.airport}</Link>
                        <span className="tabular ml-auto">{num(e.value, unit === "SM" && e.value % 1 ? 2 : 0)} {unit}</span>
                        <span className="w-20 text-right text-[11px] text-ap-text-3">{formatUtc(e.observed_at).split(", ")[1]}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </Panel>
            ))}
          </div>

          <Panel
            className="mt-4"
            title="Airport comparison"
            description={`Top ${comparison.length} airports by ${METRIC[metric].label.toLowerCase()} · bar colour = flight category`}
            actions={
              <ToggleGroup type="single" size="sm" value={metric} onValueChange={(v) => v && setMetric(v as Metric)} aria-label="Metric">
                <ToggleGroupItem value="visibility" className="px-2.5 text-xs">Visibility</ToggleGroupItem>
                <ToggleGroupItem value="wind" className="px-2.5 text-xs">Wind</ToggleGroupItem>
                <ToggleGroupItem value="temperature" className="px-2.5 text-xs">Temp</ToggleGroupItem>
              </ToggleGroup>
            }
          >
            <ToggleGroup type="single" size="sm" value={condition} onValueChange={(v) => v && setCondition(v as Condition)} aria-label="Weather condition filter" className="mb-3 flex-wrap justify-start">
              {(Object.keys(CONDITIONS) as Condition[]).map((c) => (
                <ToggleGroupItem key={c} value={c} className="px-2.5 text-xs">
                  {CONDITIONS[c].label} <span className="tabular ml-1 text-ap-text-3">{current.filter(CONDITIONS[c].test).length}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            {comparison.length === 0 ? (
              <EmptyState title="No airports currently report this condition" />
            ) : (
              <EChart
                option={compareOption}
                height={Math.max(160, comparison.length * 22)}
                ariaLabel={`${METRIC[metric].label} by airport`}
                table={{ columns: ["Airport", "Category", `${METRIC[metric].label} (${METRIC[metric].unit})`], rows: comparison.map((a) => [a.iata_code, a.flight_category, METRIC[metric].value(a)]) }}
              />
            )}
          </Panel>

          <Panel
            className="mt-4"
            title="Hourly trends (observed)"
            description="Per-hour aggregates from stored METARs: minimum visibility, maximum wind/gust, or mean temperature."
            actions={
              <ToggleGroup type="single" size="sm" value={String(hours)} onValueChange={(v) => v && setHours(Number(v))} aria-label="Trend window">
                {[24, 48, 168].map((h) => (
                  <ToggleGroupItem key={h} value={String(h)} className="px-2.5 text-xs">{h === 168 ? "7d" : `${h}h`}</ToggleGroupItem>
                ))}
              </ToggleGroup>
            }
          >
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {trendAirports.map((c, i) => (
                <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-ap-line py-0.5 pl-2 pr-1 text-xs">
                  <span className="size-2 rounded-full" style={{ background: HEX.series[i % HEX.series.length] }} aria-hidden />
                  <span className="font-mono">{c}</span>
                  <button type="button" aria-label={`Remove ${c}`} className="rounded-full p-0.5 hover:bg-white/10" onClick={() => setTrendAirports((s) => s.filter((x) => x !== c))}>
                    <X className="size-3" />
                  </button>
                </span>
              ))}
              {trendAirports.length < 6 && (
                <Select value="" onValueChange={(v) => setTrendAirports((s) => (s.includes(v) ? s : [...s, v]))}>
                  <SelectTrigger size="sm" className="h-7 w-[130px] text-xs" aria-label="Add airport to trend">
                    <SelectValue placeholder="+ Add airport" />
                  </SelectTrigger>
                  <SelectContent>
                    {allCodes.filter((c) => !trendAirports.includes(c)).map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            {trendAirports.length === 0 ? (
              <EmptyState title="Add an airport to see its trend" />
            ) : trends.isError ? (
              <ErrorState error={trends.error} onRetry={() => trends.refetch()} />
            ) : !trends.data ? (
              <PanelSkeleton className="border-0 p-0 shadow-none" lines={4} />
            ) : Math.max(0, ...trendSeries.map((s) => s.hourly.length)) < 2 ? (
              <EmptyState title="Not enough history yet">
                Hourly trends need at least two hours of stored observations for the selected airports. They fill in automatically as ingestion continues.
              </EmptyState>
            ) : (
              <EChart
                option={trendOption}
                height={280}
                ariaLabel={`Hourly ${METRIC[metric].label} for ${trendAirports.join(", ")}`}
                table={{
                  columns: ["Hour (UTC)", ...trendSeries.map((s) => s.airport)],
                  rows: Array.from(new Set(trendSeries.flatMap((s) => s.hourly.map((h) => h.hour_utc)))).sort().reverse().map((hr) => [formatUtc(hr), ...trendSeries.map((s) => { const h = s.hourly.find((x) => x.hour_utc === hr); return h ? METRIC[metric].hourly(h) : null; })]),
                }}
              />
            )}
            <p className="mt-2 text-[11px] text-ap-text-3">History begins when AeroPulse started ingesting; earlier hours are not back-filled from other sources.</p>
          </Panel>

          <Panel className="mt-4" title="FAA advisories × observed IFR/LIFR" description="Airports where an active FAA advisory coincides with IFR/LIFR conditions. Co-occurrence only — the FAA reason text states the actual cause.">
            {o.advisory_weather_overlap.length === 0 ? (
              <p className="text-sm text-ap-text-2">No airport currently has both an active FAA advisory and IFR/LIFR conditions.</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {o.advisory_weather_overlap.map((c) => {
                  const a = o.airports.find((x) => x.iata_code === c)!;
                  return (
                    <li key={c}>
                      <Link href={`/airports/${c}`} className="flex items-center gap-2 rounded-lg border border-ap-line px-3 py-2 text-sm hover:bg-white/5">
                        <span className="font-mono font-semibold">{c}</span>
                        <CategoryBadge category={a.flight_category} />
                        <RiskBadge risk={a.weather_risk} />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        </>
      )}
    </PageContainer>
  );
}
