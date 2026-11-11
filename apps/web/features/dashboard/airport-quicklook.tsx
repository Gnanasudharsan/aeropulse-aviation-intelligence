"use client";

import { ArrowUpRight, X } from "lucide-react";
import Link from "next/link";

import { CategoryBadge, RiskBadge, StatusBadge } from "@/components/data/badges";
import { Button } from "@/components/ui/button";
import { useNow } from "@/hooks/use-now";
import type { AirportSummary } from "@/lib/api/schemas";
import { cToF, num, relativeTime } from "@/lib/format";

export function AirportQuicklook({ airport, onClose }: { airport: AirportSummary; onClose: () => void }) {
  const now = useNow();
  const a = airport;
  const flags = [
    a.has_ground_stop && "Ground stop",
    a.has_ground_delay_program && "Ground delay program",
    a.has_full_closure && "Airport closure",
    a.has_reported_delay && "Reported delays",
    a.has_partial_closure && "Partial closure NOTAM",
  ].filter(Boolean) as string[];
  return (
    <div className="space-y-4" aria-live="polite">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-2xl font-semibold tracking-tight">{a.iata_code}</p>
          <p className="text-sm text-ap-text-2">{a.name}</p>
          <p className="text-xs text-ap-text-3">
            {a.city}, {a.state} · {a.icao_code}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close airport details">
          <X className="size-4" />
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <StatusBadge status={a.status} />
        <CategoryBadge category={a.weather_is_stale ? null : a.flight_category} />
        <RiskBadge risk={a.weather_risk} />
      </div>
      <p className="text-xs text-ap-text-2">{a.status_reason}</p>
      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-ap-line p-3 text-sm">
        <div>
          <dt className="text-[11px] text-ap-text-3">Visibility</dt>
          <dd className="tabular">{num(a.visibility_sm, a.visibility_sm !== null && a.visibility_sm % 1 ? 2 : 0, " SM")}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-ap-text-3">Ceiling</dt>
          <dd className="tabular">{a.ceiling_ft === null ? "None reported" : num(a.ceiling_ft, 0, " ft")}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-ap-text-3">Wind</dt>
          <dd className="tabular">
            {a.wind_speed_kt === null ? "—" : `${a.wind_speed_kt}${a.wind_gust_kt ? ` G${a.wind_gust_kt}` : ""} kt`}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-ap-text-3">Temperature</dt>
          <dd className="tabular">
            {num(a.temperature_c, 0, "°C")} <span className="text-ap-text-3">/ {num(cToF(a.temperature_c), 0, "°F")}</span>
          </dd>
        </div>
      </dl>
      <div className="space-y-1 text-xs">
        <p className="text-ap-text-3">FAA advisories ({a.active_advisories})</p>
        {flags.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {flags.map((f) => (
              <li key={f} className="rounded-md bg-white/5 px-2 py-0.5 text-ap-text-2">
                {f}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ap-text-2">None reported by FAA NAS Status.</p>
        )}
      </div>
      <p className="text-[11px] text-ap-text-3">
        METAR observed {relativeTime(a.weather_observed_at, now)}
        {a.weather_is_stale && " — stale (older than 2 h)"}
      </p>
      <Button asChild className="w-full gap-1.5">
        <Link href={`/airports/${a.iata_code}`}>
          Open airport intelligence <ArrowUpRight className="size-4" />
        </Link>
      </Button>
    </div>
  );
}
