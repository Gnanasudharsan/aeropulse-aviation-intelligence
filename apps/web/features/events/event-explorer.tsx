"use client";

import { ChevronLeft, ChevronRight, Download, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { AdvisoryTypeBadge } from "@/components/data/badges";
import { FreshnessStrip } from "@/components/data/freshness-strip";
import { EmptyState, ErrorState, PanelSkeleton } from "@/components/data/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useNow } from "@/hooks/use-now";
import { buildUrl } from "@/lib/api/client";
import { useAdvisories, useEvents } from "@/lib/api/hooks";
import { ADVISORY_LABELS, EVENT_LABELS } from "@/lib/domain";
import { formatUtc, relativeTime } from "@/lib/format";

import { AdvisorySheet } from "./advisory-sheet";

const WINDOWS = { "1h": 1, "24h": 24, "7d": 168, "30d": 720, all: 0 } as const;
type Window = keyof typeof WINDOWS;
const PAGE_SIZE = 25;

function Pager({ page, totalPages, total, onPage }: { page: number; totalPages: number; total: number; onPage: (p: number) => void }) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-ap-line px-4 py-3 text-xs text-ap-text-3">
      <span className="tabular">
        {total.toLocaleString()} record{total === 1 ? "" : "s"} · page {page} of {totalPages}
      </span>
      <div className="flex gap-1">
        <Button size="icon" variant="ghost" className="size-7" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft className="size-4" />
        </Button>
        <Button size="icon" variant="ghost" className="size-7" disabled={page >= totalPages} onClick={() => onPage(page + 1)} aria-label="Next page">
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

/** Reads ?airport= and ?advisory= — rendered inside <Suspense> by the page. */
export function EventExplorer() {
  const params = useSearchParams();
  const now = useNow();
  const [tab, setTab] = useState<"log" | "advisories">("log");
  const [airport, setAirport] = useState(params.get("airport")?.toUpperCase() ?? "");
  const [type, setType] = useState<string>("all");
  const [eventType, setEventType] = useState<string>("all");
  const [state, setState] = useState<"active" | "inactive" | "all">("all");
  const [windowKey, setWindowKey] = useState<Window>("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(params.get("advisory") ? Number(params.get("advisory")) : null);

  // Window start is computed in the event handler (never by reading the clock during render).
  const [since, setSince] = useState<string | undefined>(undefined);
  const chooseWindow = (w: Window) => {
    setWindowKey(w);
    setSince(WINDOWS[w] ? new Date(Date.now() - WINDOWS[w] * 3600_000).toISOString() : undefined);
    setPage(1);
  };

  const ap = /^[A-Z0-9]{3,4}$/.test(airport) ? airport : undefined;
  const types = type === "all" ? undefined : [type];
  const events = useEvents({ airport: ap, type: types, event_type: eventType === "all" ? undefined : [eventType], since, sort, page, page_size: PAGE_SIZE });
  const advisories = useAdvisories({ state, airport: ap, type: types, q: q || undefined, since, sort: "last_seen", page, page_size: PAGE_SIZE });

  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(1);
  };
  const csvUrl = buildUrl("/api/v1/operations/events", { airport: ap, type: types, event_type: eventType === "all" ? undefined : [eventType], since, sort, format: "csv" });

  const active = tab === "log" ? events : advisories;
  const meta = active.data?.meta;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Live Event Explorer · FAA NAS Status"
        title="Operational events"
        description="Every FAA advisory AeroPulse has observed, with its full lifecycle. Times marked FAA come from the source; detection times come from our 5-minute polling."
        meta={<FreshnessStrip dataUpdatedAt={active.dataUpdatedAt || undefined} />}
        actions={
          <Button variant="outline" size="sm" asChild className="gap-1.5">
            <a href={csvUrl} download>
              <Download className="size-3.5" /> Export CSV
            </a>
          </Button>
        }
      />

      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={tab}
        onValueChange={(v) => { if (v) { setTab(v as "log" | "advisories"); setPage(1); } }}
        aria-label="View"
        className="mb-3"
      >
        <ToggleGroupItem value="log" className="px-3 text-xs">Change log</ToggleGroupItem>
        <ToggleGroupItem value="advisories" className="px-3 text-xs">Advisories</ToggleGroupItem>
      </ToggleGroup>

      <div className="ap-panel mb-3 grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-6">
        <label className="relative">
          <span className="sr-only">Airport code</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ap-text-3" aria-hidden />
          <Input value={airport} onChange={(e) => reset(setAirport)(e.target.value.toUpperCase().slice(0, 4))} placeholder="Airport (e.g. EWR)" className="h-8 bg-ap-bg/60 pl-8 font-mono text-xs" />
        </label>
        <Select value={type} onValueChange={reset(setType)}>
          <SelectTrigger size="sm" aria-label="Advisory type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All advisory types</SelectItem>
            {Object.entries(ADVISORY_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
        {tab === "log" ? (
          <Select value={eventType} onValueChange={reset(setEventType)}>
            <SelectTrigger size="sm" aria-label="Change type"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All changes</SelectItem>
              {Object.entries(EVENT_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        ) : (
          <Select value={state} onValueChange={(v) => reset(setState)(v as typeof state)}>
            <SelectTrigger size="sm" aria-label="Advisory state"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Active + inactive</SelectItem>
              <SelectItem value="active">Active now</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        )}
        <Select value={windowKey} onValueChange={(v) => chooseWindow(v as Window)}>
          <SelectTrigger size="sm" aria-label="Time window"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="1h">Last hour</SelectItem>
            <SelectItem value="24h">Last 24 hours</SelectItem>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
            <SelectItem value="all">All time</SelectItem>
          </SelectContent>
        </Select>
        {tab === "log" ? (
          <Select value={sort} onValueChange={(v) => reset(setSort)(v as typeof sort)}>
            <SelectTrigger size="sm" aria-label="Sort"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">Newest first</SelectItem>
              <SelectItem value="oldest">Oldest first</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input value={q} onChange={(e) => reset(setQ)(e.target.value)} placeholder="Search reason / text" className="h-8 bg-ap-bg/60 text-xs" aria-label="Search advisory text" />
        )}
        <Button variant="ghost" size="sm" className="text-xs" onClick={() => { setAirport(""); setType("all"); setEventType("all"); setState("all"); chooseWindow("all"); setQ(""); setPage(1); }}>
          Clear filters
        </Button>
      </div>

      {active.isError ? (
        <ErrorState error={active.error} onRetry={() => active.refetch()} />
      ) : !active.data ? (
        <PanelSkeleton lines={8} />
      ) : active.data.data.length === 0 ? (
        <EmptyState title="No matching records">
          {tab === "log" ? "No advisory changes match these filters. Changes accumulate as FAA events are reported and cleared." : "No advisories match these filters."}
        </EmptyState>
      ) : (
        <div className="ap-panel overflow-hidden">
          <div className="overflow-x-auto">
            {tab === "log" && events.data ? (
              <table className="w-full min-w-[720px] text-sm">
                <caption className="sr-only">Advisory change log</caption>
                <thead className="bg-ap-surface-2/60 text-left text-xs text-ap-text-3">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">Detected (UTC)</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Airport</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Advisory</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Change</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Details</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">FAA updated</th>
                  </tr>
                </thead>
                <tbody>
                  {events.data.data.map((e) => (
                    <tr key={e.id} className="cursor-pointer border-t border-ap-line hover:bg-white/[0.025]" onClick={() => setOpenId(e.advisory_id)}>
                      <td className="tabular px-4 py-2.5 text-ap-text-2">
                        <button type="button" className="text-left" onClick={() => setOpenId(e.advisory_id)}>
                          {formatUtc(e.detected_at)}
                          <span className="block text-[11px] text-ap-text-3">{relativeTime(e.detected_at, now)}</span>
                        </button>
                      </td>
                      <td className="px-3 py-2.5 font-mono font-semibold">{e.airport_code}</td>
                      <td className="px-3 py-2.5"><AdvisoryTypeBadge type={e.advisory_type} /></td>
                      <td className="px-3 py-2.5">{EVENT_LABELS[e.event_type] ?? e.event_type}</td>
                      <td className="max-w-[260px] truncate px-3 py-2.5 text-xs text-ap-text-3">
                        {Object.keys(e.changes).filter((k) => k !== "type").join(", ").replaceAll("_", " ") || "—"}
                      </td>
                      <td className="tabular px-4 py-2.5 text-xs text-ap-text-3">{formatUtc(e.source_updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : advisories.data ? (
              <table className="w-full min-w-[760px] text-sm">
                <caption className="sr-only">FAA advisories</caption>
                <thead className="bg-ap-surface-2/60 text-left text-xs text-ap-text-3">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">Airport</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Type</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">State</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Reason / text</th>
                    <th scope="col" className="px-3 py-2.5 font-medium">Starts (FAA)</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Last seen</th>
                  </tr>
                </thead>
                <tbody>
                  {advisories.data.data.map((a) => (
                    <tr key={a.id} className="cursor-pointer border-t border-ap-line hover:bg-white/[0.025]" onClick={() => setOpenId(a.id)}>
                      <td className="px-4 py-2.5 font-mono font-semibold">
                        <button type="button" onClick={() => setOpenId(a.id)}>{a.airport_code}</button>
                      </td>
                      <td className="px-3 py-2.5"><AdvisoryTypeBadge type={a.advisory_type} /></td>
                      <td className={`px-3 py-2.5 text-xs ${a.is_active ? "text-ap-warn" : "text-ap-ok"}`}>{a.is_active ? "Active" : "Inactive"}</td>
                      <td className="max-w-[320px] truncate px-3 py-2.5 text-xs text-ap-text-2">{a.reason ?? a.text ?? "—"}</td>
                      <td className="tabular px-3 py-2.5 text-xs text-ap-text-3">{formatUtc(a.starts_at)}</td>
                      <td className="tabular px-4 py-2.5 text-xs text-ap-text-3">{relativeTime(a.last_seen_at, now)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
          {meta && <Pager page={meta.page ?? 1} totalPages={meta.total_pages ?? 1} total={meta.total ?? 0} onPage={setPage} />}
        </div>
      )}
      <AdvisorySheet id={openId} onClose={() => setOpenId(null)} />
    </PageContainer>
  );
}
