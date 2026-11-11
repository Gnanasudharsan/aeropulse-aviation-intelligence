"use client";

import type { EChartsOption } from "echarts";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { axisStyle, EChart } from "@/components/charts/echart";
import { Panel } from "@/components/layout/page";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Analytics, PerfRow } from "@/lib/api/schemas";
import { HEX } from "@/lib/domain";
import { num, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const monthLabel = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" });

export type Period = "12m" | "3m" | "all" | `y${number}`;

export function periodRange(period: Period, first: string | null, last: string | null): { start?: string; end?: string } {
  if (!first || !last) return {};
  const [ly, lm] = last.split("-").map(Number);
  const back = (n: number) => {
    const d = new Date(Date.UTC(ly, lm - 1 - (n - 1), 1));
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
  };
  if (period === "all") return { start: first.slice(0, 7), end: last.slice(0, 7) };
  if (period === "3m") return { start: back(3), end: last.slice(0, 7) };
  if (period === "12m") return { start: back(12), end: last.slice(0, 7) };
  const y = period.slice(1);
  return { start: `${y}-01`, end: `${y}-12` };
}

export function PeriodControls({
  data,
  period,
  onPeriod,
  direction,
  onDirection,
}: {
  data?: Analytics;
  period: Period;
  onPeriod: (p: Period) => void;
  direction: "arrival" | "departure";
  onDirection: (d: "arrival" | "departure") => void;
}) {
  const years = useMemo(() => {
    const f = data?.coverage.first_month;
    const l = data?.coverage.last_month;
    if (!f || !l) return [];
    const out: number[] = [];
    for (let y = Number(f.slice(0, 4)); y <= Number(l.slice(0, 4)); y++) out.push(y);
    return out;
  }, [data]);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <ToggleGroup type="single" size="sm" variant="outline" value={direction} onValueChange={(v) => v && onDirection(v as "arrival" | "departure")} aria-label="Direction">
        <ToggleGroupItem value="arrival" className="px-2.5 text-xs">Arrivals</ToggleGroupItem>
        <ToggleGroupItem value="departure" className="px-2.5 text-xs">Departures</ToggleGroupItem>
      </ToggleGroup>
      <Select value={period} onValueChange={(v) => onPeriod(v as Period)}>
        <SelectTrigger size="sm" className="w-[170px]" aria-label="Period">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="12m">Latest 12 months</SelectItem>
          <SelectItem value="3m">Latest 3 months</SelectItem>
          <SelectItem value="all">All loaded months</SelectItem>
          {years.map((y) => (
            <SelectItem key={y} value={`y${y}`}>
              Calendar {y} (loaded months)
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function Delta({ cur, prev, kind, invert }: { cur: number | null | undefined; prev: number | null | undefined; kind: "pts" | "min"; invert?: boolean }) {
  if (cur == null || prev == null) return <span className="text-ap-text-3">No prior-year data loaded</span>;
  const diff = cur - prev;
  const good = invert ? diff < 0 : diff > 0;
  const Icon = Math.abs(diff) < 1e-9 ? Minus : diff > 0 ? ArrowUpRight : ArrowDownRight;
  const text = kind === "pts" ? `${diff >= 0 ? "+" : ""}${(diff * 100).toFixed(1)} pts` : `${diff >= 0 ? "+" : ""}${diff.toFixed(1)} min`;
  return (
    <span className="inline-flex items-center gap-0.5" style={{ color: Math.abs(diff) < 1e-9 ? "var(--ap-text-3)" : good ? "var(--ap-ok)" : "var(--ap-crit)" }}>
      <Icon className="size-3" aria-hidden /> {text} vs prior year
    </span>
  );
}

export function PerfKpis({ data }: { data: Analytics }) {
  const t = data.totals as PerfRow;
  const prev = data.previous_year;
  const net = data.network;
  const items = [
    { label: "Flights", value: num(t.flights), sub: prev?.flights ? `${num(prev.flights)} prior year` : "Scheduled legs" },
    { label: "On-time rate", value: pct(t.ontime_rate), sub: <Delta cur={t.ontime_rate} prev={prev?.ontime_rate} kind="pts" />, extra: net ? `Network ${pct(net.ontime_rate)}` : undefined },
    { label: "Cancellation rate", value: pct(t.cancel_rate, 2), sub: <Delta cur={t.cancel_rate} prev={prev?.cancel_rate} kind="pts" invert />, extra: net ? `Network ${pct(net.cancel_rate, 2)}` : undefined },
    { label: "Average delay", value: num(t.avg_delay_min, 1, " min"), sub: <Delta cur={t.avg_delay_min} prev={prev?.avg_delay_min} kind="min" invert />, extra: net ? `Network ${num(net.avg_delay_min, 1)} min` : undefined },
    { label: "Delayed ≥ 15 min", value: num(t.delayed_15), sub: `${num(t.diverted)} diverted · ${num(t.cancelled)} cancelled` },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {items.map((i) => (
        <div key={i.label} className="ap-panel p-4">
          <p className="text-[13px] text-ap-text-2">{i.label}</p>
          <p className="tabular mt-2 text-2xl font-semibold">{i.value}</p>
          <p className="mt-1 text-[11px]">{i.sub}</p>
          {i.extra && <p className="text-[11px] text-ap-text-3">{i.extra}</p>}
        </div>
      ))}
    </div>
  );
}

export function MonthlyTrend({ data }: { data: Analytics }) {
  const m = data.monthly;
  const x = { type: "category" as const, data: m.map((r) => monthLabel(r.month)), ...axisStyle, splitLine: { show: false } };
  const ontime: EChartsOption = {
    xAxis: x,
    yAxis: { type: "value", name: "On-time %", min: (v: { min: number }) => Math.floor(v.min * 100 - 3) / 100, axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => `${Math.round(v * 100)}%` }, ...{ axisLine: axisStyle.axisLine, splitLine: axisStyle.splitLine } },
    tooltip: { trigger: "axis", valueFormatter: (v) => (typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—") },
    series: [{ name: "On-time", type: "line", symbolSize: 7, lineStyle: { width: 2, color: HEX.accent }, itemStyle: { color: HEX.accent, borderColor: HEX.surface, borderWidth: 2 }, data: m.map((r) => r.ontime_rate) }],
  };
  const volume: EChartsOption = {
    xAxis: x,
    yAxis: { type: "value", name: "Flights", ...axisStyle, axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => `${Math.round(v / 1000)}k` } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    series: [{ name: "Flights", type: "bar", barMaxWidth: 18, itemStyle: { color: HEX.series[0], borderRadius: [4, 4, 0, 0] }, data: m.map((r) => r.flights) }],
  };
  const table = { columns: ["Month", "Flights", "On-time", "Cancel rate", "Avg delay (min)"], rows: m.map((r) => [monthLabel(r.month), r.flights, pct(r.ontime_rate), pct(r.cancel_rate, 2), r.avg_delay_min]) };
  return (
    <Panel title="Monthly trend" description="On-time rate and scheduled volume by month (separate charts — different units).">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EChart option={ontime} height={240} ariaLabel="Monthly on-time rate" table={table} />
        <EChart option={volume} height={240} ariaLabel="Monthly scheduled flights" table={table} />
      </div>
    </Panel>
  );
}

type RankKey = "ontime_rate" | "avg_delay_min" | "cancel_rate" | "flights";

export function AirportRanking({ data }: { data: Analytics }) {
  const [key, setKey] = useState<RankKey>("ontime_rate");
  const rows = useMemo(() => {
    const dir = key === "ontime_rate" || key === "flights" ? -1 : 1;
    return [...data.airports].sort((a, b) => dir * (((a[key] ?? 0) as number) - ((b[key] ?? 0) as number)));
  }, [data.airports, key]);
  const fmt = (r: (typeof rows)[number]) => (key === "ontime_rate" ? pct(r.ontime_rate) : key === "cancel_rate" ? pct(r.cancel_rate, 2) : key === "flights" ? num(r.flights) : num(r.avg_delay_min, 1));
  const max = Math.max(...rows.map((r) => Math.abs((r[key] ?? 0) as number)), 1e-9);
  return (
    <Panel
      title="Airport comparison"
      description="Best first. Bars scale to the largest value in the list."
      actions={
        <Select value={key} onValueChange={(v) => setKey(v as RankKey)}>
          <SelectTrigger size="sm" className="w-[160px]" aria-label="Rank by"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ontime_rate">On-time rate</SelectItem>
            <SelectItem value="avg_delay_min">Average delay</SelectItem>
            <SelectItem value="cancel_rate">Cancellation rate</SelectItem>
            <SelectItem value="flights">Flights</SelectItem>
          </SelectContent>
        </Select>
      }
    >
      <ol className="max-h-[420px] space-y-1 overflow-auto pr-1">
        {rows.map((r, i) => (
          <li key={r.airport}>
            <Link href={`/airports/${r.airport}`} className="grid grid-cols-[24px_44px_1fr_72px] items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-white/[0.03]">
              <span className="tabular text-xs text-ap-text-3">{i + 1}</span>
              <span className="font-mono font-semibold">{r.airport}</span>
              <span className="h-1.5 overflow-hidden rounded-full bg-white/5">
                <span className="block h-full rounded-full" style={{ width: `${(Math.abs((r[key] ?? 0) as number) / max) * 100}%`, background: HEX.series[0] }} />
              </span>
              <span className="tabular text-right text-xs">{fmt(r)}</span>
            </Link>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

export function AirportMonthHeatmap({ data }: { data: Analytics }) {
  const months = Array.from(new Set(data.airport_monthly.map((c) => c.month))).sort();
  const airports = [...data.airports].sort((a, b) => (b.ontime_rate ?? 0) - (a.ontime_rate ?? 0)).map((a) => a.airport);
  const values = data.airport_monthly.map((c) => [months.indexOf(c.month), airports.indexOf(c.airport), c.ontime_rate === null ? null : Math.round(c.ontime_rate * 1000) / 10]);
  const nums = values.map((v) => v[2]).filter((v): v is number => v !== null);
  const option: EChartsOption = {
    grid: { left: 8, right: 8, top: 8, bottom: 56, containLabel: true },
    tooltip: { trigger: "item", formatter: (p: unknown) => { const v = (p as { value: [number, number, number | null] }).value; return `${airports[v[1]]} · ${monthLabel(months[v[0]])}<br/>On-time ${v[2] ?? "—"}%`; } },
    xAxis: { type: "category", data: months.map(monthLabel), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "category", data: airports, inverse: true, ...axisStyle, axisLabel: { color: HEX.text2, fontFamily: "var(--font-geist-mono)", fontSize: 9 }, splitLine: { show: false } },
    visualMap: { min: Math.floor(Math.min(...nums, 100)), max: Math.ceil(Math.max(...nums, 0)), orient: "horizontal", left: "center", bottom: 0, itemWidth: 10, itemHeight: 140, text: ["better", "worse"], textStyle: { color: HEX.text3, fontSize: 10 }, inRange: { color: ["#3a1d2b", "#7a3550", "#1c3050", "#1a6f80", "#3ed4e8"] } },
    series: [{ type: "heatmap", data: values, itemStyle: { borderColor: HEX.surface, borderWidth: 1 }, emphasis: { itemStyle: { borderColor: HEX.text } } }],
  };
  return (
    <Panel title="Airport × month on-time heatmap" description="Arrival/departure on-time % per airport and month; airports sorted by period on-time rate.">
      <EChart
        option={option}
        height={Math.max(360, airports.length * 15 + 80)}
        ariaLabel="Heatmap of on-time rate by airport and month"
        table={{ columns: ["Airport", ...months.map(monthLabel)], rows: airports.map((a) => [a, ...months.map((m) => { const c = data.airport_monthly.find((x) => x.airport === a && x.month === m); return c?.ontime_rate == null ? null : `${(c.ontime_rate * 100).toFixed(1)}%`; })]) }}
      />
    </Panel>
  );
}

function HBars({ rows, unit, ariaLabel, color = HEX.series[0] }: { rows: { key: string; value: number }[]; unit: string; ariaLabel: string; color?: string }) {
  const total = rows.reduce((s, r) => s + r.value, 0);
  return (
    <ul className="space-y-2.5" aria-label={ariaLabel}>
      {rows.map((r) => (
        <li key={r.key} className="text-sm">
          <div className="flex justify-between gap-2">
            <span className="text-ap-text-2">{r.key}</span>
            <span className="tabular text-ap-text">
              {total ? `${((r.value / total) * 100).toFixed(1)}%` : "—"} <span className="text-xs text-ap-text-3">({num(r.value)} {unit})</span>
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
            <div className="h-full rounded-full" style={{ width: `${total ? (r.value / total) * 100 : 0}%`, background: color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function DelayDrivers({ data }: { data: Analytics }) {
  const dist: EChartsOption = {
    xAxis: { type: "category", data: data.delay_distribution.map((d) => d.key), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "value", name: "Flights", ...axisStyle, axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`) } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    series: [{ type: "bar", barMaxWidth: 36, data: data.delay_distribution.map((d, i) => ({ value: d.value, itemStyle: { color: i < 2 ? HEX.series[0] : HEX.series[1], borderRadius: [4, 4, 0, 0] } })) }],
  };
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Panel title="Delay minutes by reported cause" description="Carrier-reported attribution for flights ≥ 15 min late. Attribution is not proof of causation.">
        <HBars rows={data.causes_minutes} unit="min" ariaLabel="Delay minutes by cause" />
      </Panel>
      <Panel title="Cancellations by reported cause" description="BTS cancellation codes A–D.">
        <HBars rows={data.cancellation_causes} unit="flights" ariaLabel="Cancellations by cause" color={HEX.series[2]} />
      </Panel>
      <Panel title="Delay distribution" description="Operated, non-diverted flights by minutes late (early = negative delay).">
        <EChart option={dist} height={220} ariaLabel="Distribution of flight delays" table={{ columns: ["Bucket", "Flights"], rows: data.delay_distribution.map((d) => [d.key, d.value]) }} />
      </Panel>
    </div>
  );
}

export function TemporalPatterns({ data }: { data: Analytics }) {
  const dowOpt: EChartsOption = {
    xAxis: { type: "category", data: data.day_of_week.map((d) => DOW[d.iso_dow - 1]), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "value", min: (v: { min: number }) => Math.floor(v.min * 100 - 3) / 100, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => `${Math.round(v * 100)}%` } },
    tooltip: { trigger: "axis", valueFormatter: (v) => (typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—") },
    series: [{ name: "On-time", type: "bar", barMaxWidth: 28, itemStyle: { color: HEX.series[0], borderRadius: [4, 4, 0, 0] }, data: data.day_of_week.map((d) => d.ontime_rate) }],
  };
  const hourOpt: EChartsOption = {
    xAxis: { type: "category", data: data.hourly.map((h) => `${String(h.hour_local).padStart(2, "0")}`), name: "Scheduled local hour", nameLocation: "middle", nameGap: 28, ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "value", min: (v: { min: number }) => Math.floor(v.min * 100 - 3) / 100, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => `${Math.round(v * 100)}%` } },
    grid: { left: 8, right: 16, top: 16, bottom: 32, containLabel: true },
    tooltip: { trigger: "axis", valueFormatter: (v) => (typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—") },
    series: [{ name: "On-time", type: "line", symbolSize: 6, lineStyle: { width: 2, color: HEX.series[2] }, itemStyle: { color: HEX.series[2] }, data: data.hourly.map((h) => h.ontime_rate) }],
  };
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Panel title="Day-of-week pattern" description="On-time rate by day of week (flight date).">
        <EChart option={dowOpt} height={220} ariaLabel="On-time rate by day of week" table={{ columns: ["Day", "Flights", "On-time"], rows: data.day_of_week.map((d) => [DOW[d.iso_dow - 1], d.flights, pct(d.ontime_rate)]) }} />
      </Panel>
      <Panel title="Hour-of-day pattern" description="On-time rate by scheduled local hour; delays typically accumulate through the day.">
        <EChart option={hourOpt} height={220} ariaLabel="On-time rate by scheduled hour" table={{ columns: ["Hour", "Flights", "On-time"], rows: data.hourly.map((h) => [h.hour_local, h.flights, pct(h.ontime_rate)]) }} />
      </Panel>
    </div>
  );
}

export function CarrierTable({ data, limit = 12 }: { data: Analytics; limit?: number }) {
  return (
    <Panel title="Reporting carriers" description="Marketing/operating carrier as reported to BTS; regional partners report separately.">
      <div className="-mx-4 overflow-x-auto sm:-mx-5">
        <table className="w-full min-w-[520px] text-sm">
          <caption className="sr-only">Carrier performance</caption>
          <thead className="text-left text-xs text-ap-text-3">
            <tr>
              <th scope="col" className="px-5 py-2 font-medium">Carrier</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Flights</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">On-time</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Cancel</th>
              <th scope="col" className="px-5 py-2 text-right font-medium">Avg delay</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {data.carriers.slice(0, limit).map((c) => (
              <tr key={c.carrier_code} className="border-t border-ap-line">
                <td className="px-5 py-2"><span className="font-mono text-xs text-ap-text-3">{c.carrier_code}</span> {c.carrier_name}</td>
                <td className="px-3 py-2 text-right">{num(c.flights)}</td>
                <td className={cn("px-3 py-2 text-right")}>{pct(c.ontime_rate)}</td>
                <td className="px-3 py-2 text-right">{pct(c.cancel_rate, 2)}</td>
                <td className="px-5 py-2 text-right">{num(c.avg_delay_min, 1)} min</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
