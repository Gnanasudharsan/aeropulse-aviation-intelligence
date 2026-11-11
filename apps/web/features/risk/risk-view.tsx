"use client";

import type { EChartsOption } from "echarts";
import { FlaskConical, Info, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { axisStyle, EChart } from "@/components/charts/echart";
import { EmptyState, ErrorState, PanelSkeleton, StaleNotice } from "@/components/data/states";
import { PageContainer, PageHeader, Panel } from "@/components/layout/page";
import { Input } from "@/components/ui/input";
import { useNow } from "@/hooks/use-now";
import { useAirportRisk, useRiskOverview } from "@/lib/api/hooks";
import type { RiskScore } from "@/lib/api/schemas";
import { HEX } from "@/lib/domain";
import { formatUtc, relativeTime } from "@/lib/format";

const CATEGORY: Record<string, { label: string; color: string }> = {
  low: { label: "Low", color: "var(--ap-ok)" },
  moderate: { label: "Moderate", color: "var(--ap-warn)" },
  elevated: { label: "Elevated", color: "var(--ap-crit)" },
  high: { label: "High", color: "var(--ap-lifr)" },
};
const COMPONENT_COLOR: Record<string, string> = {
  faa: HEX.series[4],
  observed: HEX.series[0],
  forecast: HEX.series[2],
  historical: HEX.series[3],
};
const COMPONENT_ORDER = ["faa", "observed", "forecast", "historical"];

function CategoryPill({ category }: { category: string }) {
  const c = CATEGORY[category] ?? { label: category, color: "var(--ap-text-3)" };
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
      style={{ color: c.color, borderColor: `color-mix(in srgb, ${c.color} 35%, transparent)`, background: `color-mix(in srgb, ${c.color} 12%, transparent)` }}
    >
      {c.label}
    </span>
  );
}

/** Score decomposed into its components — the explanation is the visual. */
function ScoreBar({ r }: { r: RiskScore }) {
  return (
    <div className="flex h-2 w-full gap-[2px] overflow-hidden rounded-full bg-white/5" role="img" aria-label={r.components.map((c) => `${c.label} ${c.points}`).join(", ")}>
      {COMPONENT_ORDER.map((k) => {
        const c = r.components.find((x) => x.key === k);
        if (!c || c.points <= 0) return null;
        return <div key={k} style={{ width: `${c.points}%`, background: COMPONENT_COLOR[k] }} title={`${c.label}: ${c.points}`} />;
      })}
    </div>
  );
}

function Detail({ code }: { code: string }) {
  const now = useNow();
  const q = useAirportRisk(code);
  const r = q.data?.data.latest;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <PanelSkeleton className="border-0 p-0 shadow-none" lines={6} />;
  if (!r) return <EmptyState title="No score yet for this airport" />;
  const hist = q.data.data.history;
  const trend: EChartsOption = {
    grid: { left: 8, right: 12, top: 12, bottom: 8, containLabel: true },
    xAxis: { type: "time", ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "value", min: 0, max: 100, ...axisStyle },
    series: [{ name: "Risk score", type: "line", step: "end", showSymbol: false, lineStyle: { width: 2, color: HEX.accent }, areaStyle: { color: "rgba(62,212,232,0.08)" }, data: hist.map((h) => [h.computed_at, h.score]) }],
  };
  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="font-mono text-2xl font-semibold">{r.airport_iata}</p>
          <p className="text-sm text-ap-text-2">{r.name}</p>
        </div>
        <div className="text-right">
          <p className="tabular text-4xl font-semibold leading-none">{Math.round(r.score)}</p>
          <p className="mt-1"><CategoryPill category={r.category} /></p>
        </div>
      </div>
      <ul className="space-y-3">
        {COMPONENT_ORDER.map((k) => {
          const c = r.components.find((x) => x.key === k);
          if (!c) return null;
          return (
            <li key={k}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="flex items-center gap-2">
                  <span className="size-2 rounded-sm" style={{ background: COMPONENT_COLOR[k] }} aria-hidden />
                  {c.label}
                </span>
                <span className="tabular text-ap-text-2">{c.points} / {c.max_points}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/5">
                <div className="h-full rounded-full" style={{ width: `${(c.points / c.max_points) * 100}%`, background: COMPONENT_COLOR[k] }} />
              </div>
              <p className="mt-1 text-xs text-ap-text-3">{c.detail} · <span className="italic">{c.source}</span></p>
            </li>
          );
        })}
      </ul>
      {r.missing_inputs.length > 0 && (
        <p className="rounded-lg border border-ap-line p-2 text-xs text-ap-text-2">
          Missing inputs (scored as 0, not imputed): {r.missing_inputs.join(", ")}
        </p>
      )}
      {r.model_probability !== null ? (
        <div className="rounded-lg border border-ap-line p-3 text-sm">
          <p className="flex items-center gap-1.5 text-xs text-ap-text-3"><FlaskConical className="size-3.5" aria-hidden /> Model estimate ({r.model_version})</p>
          <p className="tabular mt-1 text-lg font-semibold">{(r.model_probability * 100).toFixed(0)}% <span className="text-xs font-normal text-ap-text-3">probability this departure hour is disrupted</span></p>
          <ul className="mt-2 space-y-0.5 text-xs text-ap-text-2">
            {(r.model_contributions ?? []).slice(0, 4).map((c) => (
              <li key={String(c.feature)} className="flex justify-between"><span>{String(c.feature).replaceAll("_", " ")}</span><span className="tabular">{Number(c.logit_contribution) >= 0 ? "+" : ""}{Number(c.logit_contribution).toFixed(2)}</span></li>
            ))}
          </ul>
        </div>
      ) : null}
      <div>
        <p className="mb-1 text-xs text-ap-text-3">Score history (48 h)</p>
        {hist.length < 2 ? <p className="text-xs text-ap-text-3">History accumulates every 10 minutes.</p> : <EChart option={trend} height={140} ariaLabel={`Risk score history for ${r.airport_iata}`} table={{ columns: ["Computed (UTC)", "Score", "Category"], rows: [...hist].reverse().map((h) => [formatUtc(h.computed_at), h.score, h.category]) }} />}
      </div>
      <p className="text-[11px] text-ap-text-3">
        Computed {relativeTime(r.computed_at, now)} · METAR {formatUtc(String(r.inputs_as_of.metar_observed_at ?? "")) || "—"} · TAF issued {formatUtc(String(r.inputs_as_of.taf_issued_at ?? "")) || "—"}
      </p>
      <Link href={`/airports/${r.airport_iata}`} className="text-xs text-ap-accent hover:underline">Open {r.airport_iata} intelligence →</Link>
    </div>
  );
}

export function RiskView() {
  const now = useNow();
  const q = useRiskOverview();
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const d = q.data?.data;
  const rows = useMemo(() => (d?.airports ?? []).filter((r) => !filter || `${r.airport_iata} ${r.name ?? ""}`.toLowerCase().includes(filter.toLowerCase())), [d, filter]);
  const current = selected ?? d?.airports[0]?.airport_iata ?? null;
  const model = d?.model as { version?: string; metrics?: { test?: Record<string, Record<string, number>>; beats_baseline?: boolean; n_test?: number }; test_period?: string[] } | null | undefined;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Disruption Risk Intelligence · derived indicator"
        title="Where conditions point to disruption"
        description="A transparent, rules-based indicator combining FAA-reported state, observed weather, the next 6 hours of TAF forecast, and each airport's historical delay pattern for this month and hour."
        meta={d ? <p className="text-xs text-ap-text-3">Method {d.method_version} · computed {relativeTime(d.computed_at, now)} · recomputed every 10 minutes</p> : null}
      />
      <div className="mb-4 flex items-start gap-2 rounded-lg border border-ap-line bg-ap-surface/60 px-3 py-2 text-sm text-ap-text-2">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-ap-accent" aria-hidden />
        {d?.disclaimer ?? "A risk score is not a confirmed delay and does not predict the outcome of any specific flight."}
      </div>
      {d?.is_stale && (
        <div className="mb-4"><StaleNotice>Risk scores have not been recomputed in the last 30 minutes.</StaleNotice></div>
      )}
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !d ? (
        <PanelSkeleton lines={8} />
      ) : d.airports.length === 0 ? (
        <EmptyState title="No risk scores computed yet">Scores appear after the worker&apos;s first risk run.</EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {(["high", "elevated", "moderate", "low"] as const).map((c) => (
              <div key={c} className="ap-panel p-4">
                <CategoryPill category={c} />
                <p className="tabular mt-2 text-3xl font-semibold">{d.category_counts[c] ?? 0}</p>
                <p className="text-[11px] text-ap-text-3">{{ high: "score ≥ 60", elevated: "40–59", moderate: "20–39", low: "< 20" }[c]}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
            <Panel
              className="lg:col-span-7"
              title="Airports by risk score"
              description="Bar segments show how much each input contributed."
              actions={<Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter" className="h-8 w-28 bg-ap-bg/60 text-xs" aria-label="Filter airports" />}
            >
              <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ap-text-2" aria-label="Component legend">
                {[["faa", "FAA reported"], ["observed", "Observed weather"], ["forecast", "TAF next 6 h"], ["historical", "Historical baseline"]].map(([k, l]) => (
                  <li key={k} className="flex items-center gap-1.5"><span className="size-2 rounded-sm" style={{ background: COMPONENT_COLOR[k] }} aria-hidden />{l}</li>
                ))}
              </ul>
              <ol className="max-h-[560px] space-y-0.5 overflow-auto pr-1">
                {rows.map((r) => (
                  <li key={r.airport_iata}>
                    <button
                      type="button"
                      onClick={() => setSelected(r.airport_iata)}
                      aria-pressed={current === r.airport_iata}
                      className={`grid w-full grid-cols-[44px_1fr_40px_86px] items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-white/[0.03] ${current === r.airport_iata ? "bg-ap-accent-soft" : ""}`}
                    >
                      <span className="font-mono text-sm font-semibold">{r.airport_iata}</span>
                      <ScoreBar r={r} />
                      <span className="tabular text-right text-sm">{Math.round(r.score)}</span>
                      <span className="text-right"><CategoryPill category={r.category} /></span>
                    </button>
                  </li>
                ))}
              </ol>
            </Panel>
            <Panel className="lg:col-span-5" title="Explanation">
              {current ? <Detail code={current} /> : null}
            </Panel>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel title="How the score is built (rules-v1)">
              <table className="w-full text-sm">
                <caption className="sr-only">Risk score components</caption>
                <tbody className="divide-y divide-ap-line">
                  {[
                    ["FAA reported state", "Ground stop / GDP / closure 45 · reported delays 25", "45"],
                    ["Observed weather (METAR)", "Severe 25 · high 18 · elevated 8", "25"],
                    ["Forecast (TAF, next 6 h)", "LIFR 15 / IFR 10 · thunderstorms +10 · gusts ≥ 35 kt +8 (≥ 25 kt +4)", "20"],
                    ["Historical baseline (BTS)", "(rate − 15%) × 60 for departures delayed ≥ 15 min or cancelled, this month & local hour", "15"],
                  ].map(([a, b, c]) => (
                    <tr key={a}><td className="py-2 pr-3 font-medium">{a}</td><td className="py-2 pr-3 text-ap-text-2">{b}</td><td className="tabular py-2 text-right text-ap-text-3">max {c}</td></tr>
                  ))}
                </tbody>
              </table>
            </Panel>
            <Panel title="Predictive model">
              {model ? (
                <div className="space-y-2 text-sm text-ap-text-2">
                  <p>
                    <span className="font-medium text-ap-text">{model.version}</span> — logistic regression trained on BTS departure outcomes joined with prior-hour METARs; chronological hold-out {model.test_period?.join(" → ")} ({model.metrics?.n_test?.toLocaleString()} airport-hours).
                  </p>
                  <table className="w-full text-xs">
                    <thead className="text-left text-ap-text-3"><tr><th className="py-1 font-medium">Model</th><th className="font-medium">ROC AUC</th><th className="font-medium">PR AUC</th><th className="font-medium">Brier</th></tr></thead>
                    <tbody className="tabular">
                      {Object.entries(model.metrics?.test ?? {}).map(([k, m]) => (
                        <tr key={k} className="border-t border-ap-line"><td className="py-1">{k}</td><td>{m.roc_auc}</td><td>{m.pr_auc}</td><td>{m.brier}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="text-xs">{model.metrics?.beats_baseline ? "Served alongside the rules score (beats the baseline by ≥ 0.02 AUC)." : "Not served: it did not beat the baseline by the required margin."}</p>
                </div>
              ) : (
                <p className="flex gap-2 text-sm text-ap-text-2"><Info className="mt-0.5 size-4 shrink-0" aria-hidden />No validated model artifact is deployed. Only the transparent rules baseline is shown.</p>
              )}
            </Panel>
          </div>
        </>
      )}
    </PageContainer>
  );
}
