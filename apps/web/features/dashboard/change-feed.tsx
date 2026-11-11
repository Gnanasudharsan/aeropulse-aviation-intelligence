"use client";

import { ArrowRight, CircleCheck, CirclePlus, PencilLine, RotateCcw } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/data/states";
import { useNow } from "@/hooks/use-now";
import type { OperationalEvent } from "@/lib/api/schemas";
import { ADVISORY_LABELS, EVENT_LABELS } from "@/lib/domain";
import { formatUtc, relativeTime } from "@/lib/format";

const ICONS = { created: CirclePlus, updated: PencilLine, cleared: CircleCheck, reopened: RotateCcw } as const;
const COLORS = { created: "var(--ap-warn)", updated: "var(--ap-accent)", cleared: "var(--ap-ok)", reopened: "var(--ap-warn)" } as const;

export function ChangeFeed({ events }: { events: OperationalEvent[] }) {
  const now = useNow();
  if (events.length === 0)
    return (
      <EmptyState title="No changes recorded yet">
        Changes appear here when FAA advisories are reported, updated or cleared between polls.
      </EmptyState>
    );
  return (
    <ol className="relative space-y-0.5">
      {events.map((e) => {
        const kind = (e.event_type in ICONS ? e.event_type : "updated") as keyof typeof ICONS;
        const Icon = ICONS[kind];
        const changed = Object.keys(e.changes).filter((k) => k !== "type");
        return (
          <li key={e.id}>
            <Link
              href={`/events?advisory=${e.advisory_id}`}
              className="group flex items-start gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-white/[0.03]"
            >
              <Icon className="mt-0.5 size-4 shrink-0" style={{ color: COLORS[kind] }} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-ap-text">
                  <span className="font-mono font-semibold">{e.airport_code}</span>{" "}
                  <span className="text-ap-text-2">{ADVISORY_LABELS[e.advisory_type] ?? e.advisory_type}</span>{" "}
                  <span className="text-ap-text-3">· {EVENT_LABELS[e.event_type] ?? e.event_type}</span>
                </p>
                {changed.length > 0 && <p className="truncate text-xs text-ap-text-3">Changed: {changed.join(", ").replaceAll("_", " ")}</p>}
              </div>
              <time dateTime={e.detected_at} title={formatUtc(e.detected_at)} className="shrink-0 text-xs text-ap-text-3">
                {relativeTime(e.detected_at, now)}
              </time>
              <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-ap-text-3 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
