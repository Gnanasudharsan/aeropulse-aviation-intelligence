"use client";

import { useIsFetching } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useNow } from "@/hooks/use-now";
import { useFreshness } from "@/lib/api/hooks";
import { HEALTH_META } from "@/lib/domain";
import { formatUtc, relativeTime } from "@/lib/format";

const LABELS: Record<string, string> = {
  faa_nas_status: "FAA NAS Status",
  awc_metar: "METAR",
  awc_taf: "TAF",
};

/**
 * Shows the distinct clocks: source observation/publication, our ingestion, and the
 * browser's last successful refresh.
 */
export function FreshnessStrip({ dataUpdatedAt }: { dataUpdatedAt?: number }) {
  const now = useNow();
  const { data, isError, error } = useFreshness();
  const notConfigured = (error as { code?: string } | null)?.code === "not_configured";
  const fetching = useIsFetching() > 0;
  const sources = data?.data.filter((s) => s.source in LABELS) ?? [];
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ap-text-2" aria-live="polite">
      {isError && (
        <span className="text-ap-crit">
          {notConfigured ? "Freshness unavailable — no live API connected to this deployment" : "Freshness unavailable — API unreachable"}
        </span>
      )}
      {sources.map((s) => {
        const meta = HEALTH_META[s.health];
        return (
          <Tooltip key={s.source}>
            <TooltipTrigger asChild>
              <button type="button" className="flex items-center gap-1.5 rounded-sm">
                <span className="size-1.5 rounded-full" style={{ background: meta.color }} aria-hidden />
                <span className="text-ap-text">{LABELS[s.source]}</span>
                <span className="text-ap-text-3">
                  {meta.label} · ingested {relativeTime(s.last_success_at, now)}
                </span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs space-y-1 text-xs">
              <p className="font-medium">{s.display_name}</p>
              <p>Last successful ingestion: {formatUtc(s.last_success_at)}</p>
              <p>Latest source observation/issue: {formatUtc(s.last_observation_at)}</p>
              <p>Source published: {formatUtc(s.last_source_published_at)}</p>
              {s.consecutive_failures > 0 && <p>Consecutive failures: {s.consecutive_failures}</p>}
            </TooltipContent>
          </Tooltip>
        );
      })}
      {dataUpdatedAt ? (
        <span className="flex items-center gap-1.5 text-ap-text-3">
          <RefreshCw className={fetching ? "size-3 animate-spin" : "size-3"} aria-hidden />
          Page refreshed {relativeTime(new Date(dataUpdatedAt).toISOString(), now)} · auto every 30 s
        </span>
      ) : null}
    </div>
  );
}
