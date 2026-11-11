"use client";

import { ExternalLink } from "lucide-react";

import { AdvisoryTypeBadge } from "@/components/data/badges";
import { useNow } from "@/hooks/use-now";
import type { Advisory } from "@/lib/api/schemas";
import { SCOPE_LABELS } from "@/lib/domain";
import { formatUtc, relativeTime } from "@/lib/format";

export function AdvisoryCard({ advisory: a }: { advisory: Advisory }) {
  const now = useNow();
  const window = Array.isArray(a.details.daily_window_utc) ? (a.details.daily_window_utc as string[]) : null;
  return (
    <article className="space-y-2 rounded-lg border border-ap-line bg-ap-bg/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <AdvisoryTypeBadge type={a.advisory_type} />
        <span className="text-[11px] text-ap-text-3">Scope: {SCOPE_LABELS[a.scope] ?? a.scope}</span>
        {!a.is_active && <span className="text-[11px] text-ap-ok">Cleared {relativeTime(a.cleared_at, now)}</span>}
      </div>
      {(a.reason || a.text) && <p className="text-sm text-ap-text">{a.reason && a.text && a.reason !== a.text ? a.reason : a.text ?? a.reason}</p>}
      {window && (
        <p className="text-xs text-ap-text-2">
          Recurring daily closure window {window[0]}–{window[1]} UTC
        </p>
      )}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
        {a.avg_delay_minutes !== null && (
          <div><dt className="text-ap-text-3">Avg delay</dt><dd className="tabular">{a.avg_delay_minutes} min</dd></div>
        )}
        {(a.min_delay_minutes !== null || a.max_delay_minutes !== null) && (
          <div><dt className="text-ap-text-3">Range</dt><dd className="tabular">{a.min_delay_minutes ?? "?"}–{a.max_delay_minutes ?? "?"} min</dd></div>
        )}
        {a.trend && <div><dt className="text-ap-text-3">Trend</dt><dd>{a.trend}</dd></div>}
        <div><dt className="text-ap-text-3">Starts</dt><dd className="tabular">{formatUtc(a.starts_at)}</dd></div>
        <div><dt className="text-ap-text-3">Ends</dt><dd className="tabular">{formatUtc(a.ends_at)}</dd></div>
        <div><dt className="text-ap-text-3">FAA updated</dt><dd className="tabular">{formatUtc(a.source_updated_at)}</dd></div>
        <div><dt className="text-ap-text-3">First seen by us</dt><dd className="tabular">{formatUtc(a.first_seen_at)}</dd></div>
      </dl>
      <a
        href={a.advisory_url ?? "https://nasstatus.faa.gov/"}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 text-[11px] text-ap-accent hover:underline"
      >
        Source: FAA NAS Status <ExternalLink className="size-3" aria-hidden />
      </a>
    </article>
  );
}
