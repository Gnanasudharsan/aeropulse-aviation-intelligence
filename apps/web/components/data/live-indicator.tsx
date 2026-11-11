"use client";

import Link from "next/link";

import { useFreshness } from "@/lib/api/hooks";
import type { SourceHealth } from "@/lib/api/schemas";
import { HEALTH_META } from "@/lib/domain";
import { cn } from "@/lib/utils";

const ORDER: SourceHealth[] = ["healthy", "delayed", "stale", "unavailable"];

/** Compact header pill summarising live-source health (worst of FAA + METAR). */
export function LiveIndicator() {
  const { data, isError, isPending, error } = useFreshness();
  const notConfigured = (error as { code?: string } | null)?.code === "not_configured";
  let health: SourceHealth | "offline" | "loading" = "loading";
  if (isError) health = "offline";
  else if (data) {
    const live = data.data.filter((s) => s.source === "faa_nas_status" || s.source === "awc_metar");
    health = live.reduce<SourceHealth>((worst, s) => (ORDER.indexOf(s.health) > ORDER.indexOf(worst) ? s.health : worst), "healthy");
  }
  const color =
    health === "loading" ? "var(--ap-text-3)" : health === "offline" ? "var(--ap-crit)" : HEALTH_META[health].color;
  const label =
    health === "loading"
      ? "Connecting"
      : health === "offline"
        ? notConfigured
          ? "API not connected"
          : "API offline"
        : health === "healthy"
          ? "Live"
          : `Data ${HEALTH_META[health].label.toLowerCase()}`;
  return (
    <Link
      href="/methodology#freshness"
      className="flex items-center gap-2 rounded-full border border-ap-line bg-ap-surface/60 px-3 py-1 text-xs text-ap-text-2 transition-colors hover:text-ap-text"
      aria-label={`Data status: ${label}`}
    >
      <span className="relative flex size-2">
        {health === "healthy" && !isPending && (
          <span className="absolute inline-flex size-full animate-ping rounded-full opacity-60" style={{ background: color }} />
        )}
        <span className={cn("relative inline-flex size-2 rounded-full")} style={{ background: color }} />
      </span>
      {label}
    </Link>
  );
}
