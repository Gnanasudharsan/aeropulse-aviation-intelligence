"use client";

import { ExternalLink } from "lucide-react";

import { HealthBadge } from "@/components/data/badges";
import { ErrorState, PanelSkeleton } from "@/components/data/states";
import { Panel } from "@/components/layout/page";
import { useNow } from "@/hooks/use-now";
import { useSystemStatus } from "@/lib/api/hooks";
import { formatUtc, relativeTime } from "@/lib/format";

function dur(seconds: number) {
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86_400 * 2) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86_400)} d`;
}

const QC: Record<string, string> = { pass: "var(--ap-ok)", warn: "var(--ap-warn)", fail: "var(--ap-crit)" };

export function SystemHealth() {
  const now = useNow();
  const { data, isError, error, refetch } = useSystemStatus();
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!data) return <PanelSkeleton lines={6} />;
  const s = data.data;
  return (
    <div className="space-y-4">
      <Panel id="freshness" title="Source freshness (live)" description="Health is derived from the age of the last successful ingestion against documented thresholds.">
        <div className="-mx-4 overflow-x-auto sm:-mx-5">
          <table className="w-full min-w-[860px] text-sm">
            <caption className="sr-only">Freshness of each upstream data source</caption>
            <thead className="text-left text-xs text-ap-text-3">
              <tr>
                <th scope="col" className="px-5 py-2 font-medium">Source</th>
                <th scope="col" className="px-3 py-2 font-medium">Health</th>
                <th scope="col" className="px-3 py-2 font-medium">Last successful ingestion</th>
                <th scope="col" className="px-3 py-2 font-medium">Latest source observation</th>
                <th scope="col" className="px-3 py-2 font-medium">Refresh</th>
                <th scope="col" className="px-5 py-2 font-medium">Thresholds (healthy / delayed / stale)</th>
              </tr>
            </thead>
            <tbody>
              {s.sources.map((src) => (
                <tr key={src.source} className="border-t border-ap-line align-top">
                  <td className="px-5 py-3">
                    <a href={src.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ap-text hover:text-ap-accent">
                      {src.display_name} <ExternalLink className="size-3" aria-hidden />
                    </a>
                    <p className="mt-1 max-w-sm text-xs leading-relaxed text-ap-text-3">{src.limitations}</p>
                    {src.last_error && <p className="mt-1 max-w-sm text-xs text-ap-crit">Last error: {src.last_error}</p>}
                  </td>
                  <td className="px-3 py-3"><HealthBadge health={src.health} /></td>
                  <td className="tabular px-3 py-3 text-xs">
                    {formatUtc(src.last_success_at)}
                    <span className="block text-ap-text-3">{relativeTime(src.last_success_at, now)}</span>
                  </td>
                  <td className="tabular px-3 py-3 text-xs">
                    {formatUtc(src.last_observation_at)}
                    <span className="block text-ap-text-3">{src.last_record_count !== null ? `${src.last_record_count} records last run` : ""}</span>
                  </td>
                  <td className="tabular px-3 py-3 text-xs">every {dur(src.expected_interval_seconds)}</td>
                  <td className="tabular px-5 py-3 text-xs text-ap-text-2">
                    ≤ {dur(src.thresholds_seconds.healthy)} / ≤ {dur(src.thresholds_seconds.delayed)} / ≤ {dur(src.thresholds_seconds.stale)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Recent ingestion runs" description="Every run is audited in ingestion_runs.">
          <ul className="divide-y divide-ap-line text-xs">
            {s.recent_runs.map((r) => (
              <li key={r.id} className="flex items-center gap-3 py-2">
                <span className="w-12 font-mono uppercase text-ap-text-2">{r.job}</span>
                <span className={r.status === "success" ? "text-ap-ok" : r.status === "partial" ? "text-ap-warn" : "text-ap-crit"}>{r.status}</span>
                <span className="tabular text-ap-text-3">{r.records_fetched} fetched · {r.records_inserted} new · {r.records_updated} changed</span>
                <span className="tabular ml-auto text-ap-text-3">{relativeTime(r.started_at, now)}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Latest data-quality checks" description="From the most recent run of each source.">
          <ul className="divide-y divide-ap-line text-xs">
            {s.latest_quality.map((q) => (
              <li key={`${q.source}-${q.check_name}`} className="flex items-start gap-3 py-2">
                <span className="mt-1 size-1.5 shrink-0 rounded-full" style={{ background: QC[q.status] }} aria-hidden />
                <span className="w-24 shrink-0 text-ap-text-3">{q.source}</span>
                <span className="flex-1">
                  <span className="text-ap-text">{q.check_name.replaceAll("_", " ")}</span>{" "}
                  <span className="text-ap-text-3">
                    = {q.observed_value ?? "—"}
                    {q.threshold ? ` (target ${q.threshold})` : ""}
                  </span>
                  {q.message && <span className="block truncate text-ap-text-3" title={q.message}>{q.message}</span>}
                </span>
                <span className="uppercase" style={{ color: QC[q.status] }}>{q.status}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
