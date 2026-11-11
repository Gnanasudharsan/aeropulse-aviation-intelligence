"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { AdvisoryTypeBadge } from "@/components/data/badges";
import { ErrorState, PanelSkeleton } from "@/components/data/states";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useAdvisoryDetail } from "@/lib/api/hooks";
import { EVENT_LABELS, SCOPE_LABELS } from "@/lib/domain";
import { formatUtc } from "@/lib/format";

export function AdvisorySheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const q = useAdvisoryDetail(id);
  const a = q.data?.data;
  return (
    <Sheet open={id !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto border-ap-line bg-ap-bg-elevated sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{a ? `${a.airport_code} · Advisory #${a.id}` : "Advisory"}</SheetTitle>
          <SheetDescription>Lifecycle as detected by AeroPulse polling of FAA NAS Status.</SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-8">
          {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
          {!a && !q.isError && <PanelSkeleton lines={6} />}
          {a && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <AdvisoryTypeBadge type={a.advisory_type} />
                <span className="text-xs text-ap-text-3">Scope: {SCOPE_LABELS[a.scope] ?? a.scope}</span>
                <span className={`text-xs ${a.is_active ? "text-ap-warn" : "text-ap-ok"}`}>{a.is_active ? "Active" : "Inactive"}</span>
              </div>
              {(a.text || a.reason) && <p className="rounded-lg bg-ap-bg/60 p-3 font-mono text-xs leading-relaxed text-ap-text-2">{a.text ?? a.reason}</p>}
              <dl className="grid grid-cols-2 gap-3 text-xs">
                {[
                  ["Event start (FAA)", formatUtc(a.starts_at)],
                  ["Event end (FAA)", formatUtc(a.ends_at)],
                  ["FAA last updated", formatUtc(a.source_updated_at)],
                  ["First seen by AeroPulse", formatUtc(a.first_seen_at)],
                  ["Last seen in feed", formatUtc(a.last_seen_at)],
                  ["Cleared (absent from feed)", formatUtc(a.cleared_at)],
                  ["Average delay", a.avg_delay_minutes !== null ? `${a.avg_delay_minutes} min` : "—"],
                  ["Feed", a.source_feed === "faa_json" ? "airport-events (JSON)" : "airport-status (XML)"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-ap-text-3">{k}</dt>
                    <dd className="tabular text-ap-text">{v}</dd>
                  </div>
                ))}
              </dl>
              <div>
                <h3 className="mb-2 text-xs font-medium text-ap-text-2">Timeline</h3>
                <ol className="relative space-y-3 border-l border-ap-line pl-4">
                  {a.timeline.map((e) => (
                    <li key={e.id} className="relative">
                      <span className="absolute -left-[21px] top-1 size-2.5 rounded-full border-2 border-ap-bg-elevated bg-ap-accent" aria-hidden />
                      <p className="text-sm text-ap-text">{EVENT_LABELS[e.event_type] ?? e.event_type}</p>
                      <p className="tabular text-xs text-ap-text-3">{formatUtc(e.detected_at)}</p>
                      {Object.entries(e.changes)
                        .filter(([k]) => k !== "type")
                        .map(([k, v]) => {
                          const change = v as { from?: unknown; to?: unknown };
                          return (
                            <p key={k} className="text-xs text-ap-text-2">
                              {k.replaceAll("_", " ")}: <span className="text-ap-text-3">{String(change.from ?? "—")}</span> → {String(change.to ?? "—")}
                            </p>
                          );
                        })}
                    </li>
                  ))}
                </ol>
              </div>
              <div className="flex flex-wrap gap-3 text-xs">
                {a.airport_iata && (
                  <Link href={`/airports/${a.airport_iata}`} className="text-ap-accent hover:underline">
                    Open {a.airport_iata} intelligence →
                  </Link>
                )}
                <a href={a.advisory_url ?? a.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ap-accent hover:underline">
                  FAA source <ExternalLink className="size-3" aria-hidden />
                </a>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
