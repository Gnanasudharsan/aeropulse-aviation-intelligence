"use client";

import { AnimatedNumber } from "@/components/data/kpi";
import { AirportMap } from "@/components/map/airport-map";
import { MapLegend } from "@/components/map/map-legend";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";
import { useAirports, useOperationsSummary } from "@/lib/api/hooks";
import { relativeTime } from "@/lib/format";

export function LiveStats() {
  const now = useNow();
  const summary = useOperationsSummary();
  const airports = useAirports();
  const s = summary.data?.data;
  const lowWx = airports.data?.data.filter((a) => !a.weather_is_stale && (a.flight_category === "IFR" || a.flight_category === "LIFR")).length;
  const stats: [string, number | undefined][] = [
    ["Airports monitored", s?.monitored_airports],
    ["With FAA advisories", s?.airports_with_active_advisories],
    ["FAA programs active", s ? s.active_ground_stops + s.active_ground_delay_programs : undefined],
    ["IFR / LIFR now", lowWx],
  ];
  if (summary.isError)
    return (
      <p className="text-sm text-ap-text-3">
        {(summary.error as { code?: string }).code === "not_configured"
          ? "Live figures are not shown: this deployment is not connected to a live API. See the screenshots and setup in the README."
          : "Live figures are unavailable right now — the API could not be reached."}
      </p>
    );
  return (
    <div>
      <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
        {stats.map(([label, v]) => (
          <div key={label}>
            <dt className="text-xs text-ap-text-3">{label}</dt>
            <dd className="mt-1 text-2xl font-semibold text-ap-text">
              {v === undefined ? <Skeleton className="h-7 w-10 bg-white/5" /> : <AnimatedNumber value={v} />}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-[11px] text-ap-text-3">
        Real values from our API · FAA ingested {relativeTime(s?.faa_last_success_at, now)} · latest METAR {relativeTime(s?.latest_observation_at, now)}
      </p>
    </div>
  );
}

export function HeroMap() {
  const airports = useAirports();
  return (
    <div className="relative">
      <div className="absolute -inset-6 rounded-[32px] bg-[radial-gradient(ellipse_at_center,rgba(62,212,232,0.18),transparent_65%)] blur-2xl" aria-hidden />
      <div className="ap-panel relative overflow-hidden p-2">
        <AirportMap airports={airports.data?.data ?? []} interactive={false} className="h-[300px] sm:h-[380px]" />
        <div className="absolute bottom-4 left-4 right-4 rounded-lg bg-ap-bg/80 px-3 py-2 backdrop-blur">
          <MapLegend mode="status" />
        </div>
      </div>
    </div>
  );
}
