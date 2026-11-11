"use client";

import { ArrowLeft, Compass, Gauge, Navigation, Thermometer, Wind, Eye, Cloud } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CategoryBadge, RiskBadge, StatusBadge } from "@/components/data/badges";
import { FreshnessStrip } from "@/components/data/freshness-strip";
import { EmptyState, ErrorState, PanelSkeleton, StaleNotice } from "@/components/data/states";
import { PageContainer, PageHeader, Panel } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useNow } from "@/hooks/use-now";
import { ApiError } from "@/lib/api/client";
import { useAirport, useAirportAdvisories, useAirportWeather } from "@/lib/api/hooks";
import { CATEGORY_META } from "@/lib/domain";
import { cToF, formatLocal, formatUtc, num, relativeTime, visibility, wind } from "@/lib/format";

import { AdvisoryCard } from "./advisory-card";
import { TafTimeline } from "./taf-timeline";
import { ObservationCharts } from "./weather-charts";

function Metric({ icon: Icon, label, value, sub }: { icon: typeof Wind; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-ap-line bg-ap-bg/40 p-3">
      <p className="flex items-center gap-1.5 text-[11px] text-ap-text-3">
        <Icon className="size-3.5" aria-hidden /> {label}
      </p>
      <p className="tabular mt-1 text-lg font-semibold text-ap-text">{value}</p>
      {sub && <p className="text-[11px] text-ap-text-3">{sub}</p>}
    </div>
  );
}

export function AirportView({ code }: { code: string }) {
  const now = useNow();
  const [hours, setHours] = useState(24);
  const airport = useAirport(code);
  const weather = useAirportWeather(code, hours);
  const history = useAirportAdvisories(code);

  if (airport.isError) {
    const notFound = airport.error instanceof ApiError && (airport.error.status === 404 || airport.error.status === 422);
    return (
      <PageContainer className="py-16">
        {notFound ? (
          <EmptyState title={`${code} is not a monitored airport`} icon={<Compass className="size-7 text-ap-text-3" aria-hidden />}>
            AeroPulse monitors 50 major U.S. airports.{" "}
            <Link href="/airports" className="text-ap-accent hover:underline">
              Browse the list
            </Link>
            .
          </EmptyState>
        ) : (
          <ErrorState error={airport.error} onRetry={() => airport.refetch()} />
        )}
      </PageContainer>
    );
  }
  const a = airport.data?.data;
  if (!a) {
    return (
      <PageContainer className="space-y-4 py-10">
        <PanelSkeleton lines={2} />
        <PanelSkeleton lines={6} />
      </PageContainer>
    );
  }
  const w = a.latest_weather;
  const ceilingLayer = w?.cloud_layers.find((l) => l.base_ft === w.ceiling_ft && ["BKN", "OVC", "OVX"].includes(l.cover ?? ""));
  const pastAdvisories = history.data?.data.filter((x) => !x.is_active) ?? [];

  return (
    <PageContainer>
      <Link href="/airports" className="mt-6 inline-flex items-center gap-1 text-xs text-ap-text-3 hover:text-ap-text">
        <ArrowLeft className="size-3.5" aria-hidden /> All airports
      </Link>
      <PageHeader
        eyebrow={`${a.icao_code} · ${a.city}, ${a.state} · ${a.timezone.replace("_", " ")}`}
        title={
          <span className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-mono">{a.iata_code}</span>
            <span className="text-lg font-normal text-ap-text-2 sm:text-xl">{a.name}</span>
          </span>
        }
        meta={
          <div className="space-y-3">
            <div className="flex flex-wrap gap-1.5">
              <StatusBadge status={a.status} />
              <CategoryBadge category={a.weather_is_stale ? null : a.flight_category} />
              <RiskBadge risk={a.weather_risk} />
            </div>
            <p className="text-sm text-ap-text-2">{a.status_reason}</p>
            <FreshnessStrip dataUpdatedAt={airport.dataUpdatedAt || undefined} />
          </div>
        }
      />

      {a.weather_is_stale && w && (
        <div className="mb-4">
          <StaleNotice>
            The latest METAR for {a.iata_code} was observed {relativeTime(w.observed_at, now)}. Conditions shown may no longer be current.
          </StaleNotice>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-12">
        <Panel
          className="lg:col-span-8"
          title="Current conditions (observed)"
          description={w ? `METAR observed ${formatUtc(w.observed_at)} · ${formatLocal(w.observed_at, a.timezone)}` : undefined}
        >
          {!w ? (
            <EmptyState title="No observation stored yet">METARs appear here after the next weather ingestion.</EmptyState>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                <div className="rounded-lg border border-ap-line p-3" style={{ background: w.flight_category ? `color-mix(in srgb, ${CATEGORY_META[w.flight_category]?.color} 10%, transparent)` : undefined }}>
                  <p className="text-[11px] text-ap-text-3">Flight category</p>
                  <p className="mt-1 text-lg font-semibold" style={{ color: w.flight_category ? CATEGORY_META[w.flight_category]?.color : undefined }}>
                    {w.flight_category ?? "—"}
                  </p>
                  <p className="text-[11px] text-ap-text-3">{w.flight_category_source === "awc" ? "per AWC" : "derived"}</p>
                </div>
                <Metric icon={Eye} label="Visibility" value={visibility(w.visibility_sm, w.visibility_text, w.visibility_is_lower_bound)} />
                <Metric icon={Cloud} label="Ceiling" value={w.ceiling_ft === null ? "None" : `${num(w.ceiling_ft)} ft`} sub={ceilingLayer ? `${ceilingLayer.cover} layer` : "no BKN/OVC layer"} />
                <Metric icon={Wind} label="Wind" value={wind(w.wind_dir_deg, w.wind_dir_variable, w.wind_speed_kt, w.wind_gust_kt)} />
                <Metric icon={Thermometer} label="Temp / dew" value={`${num(w.temperature_c, 0)}° / ${num(w.dewpoint_c, 0)}°C`} sub={`${num(cToF(w.temperature_c))}°F`} />
                <Metric icon={Gauge} label="Altimeter" value={w.altimeter_hpa === null ? "—" : `${num(w.altimeter_hpa, 1)} hPa`} sub={w.altimeter_hpa ? `${(w.altimeter_hpa * 0.02953).toFixed(2)} inHg` : undefined} />
              </div>
              {w.wx_string && (
                <p className="text-sm text-ap-text-2">
                  Present weather: <span className="font-mono text-ap-text">{w.wx_string}</span>
                </p>
              )}
              <div>
                <p className="mb-1 text-[11px] text-ap-text-3">Raw {w.metar_type}</p>
                <pre className="whitespace-pre-wrap break-all rounded-lg bg-ap-bg/70 p-3 font-mono text-xs leading-relaxed text-ap-text-2">{w.raw_text}</pre>
              </div>
              <dl className="grid grid-cols-1 gap-2 text-[11px] text-ap-text-3 sm:grid-cols-3">
                <div><dt>Observed (source clock)</dt><dd className="text-ap-text-2">{formatUtc(w.observed_at)}</dd></div>
                <div><dt>Received by AWC</dt><dd className="text-ap-text-2">{formatUtc(w.source_published_at)}</dd></div>
                <div><dt>Ingested by AeroPulse</dt><dd className="text-ap-text-2">{formatUtc(w.ingested_at)}</dd></div>
              </dl>
            </div>
          )}
        </Panel>

        <div className="flex flex-col gap-4 lg:col-span-4">
          <Panel title="Observed weather risk" description="Derived from the latest METAR only. Describes conditions; it is not a delay prediction.">
            <div className="space-y-2">
              <RiskBadge risk={a.weather_risk} />
              <ul className="space-y-1 text-sm text-ap-text-2">
                {a.weather_risk_factors.map((f) => (
                  <li key={f} className="flex gap-2"><Navigation className="mt-1 size-3 shrink-0 rotate-90 text-ap-text-3" aria-hidden />{f}</li>
                ))}
              </ul>
            </div>
          </Panel>
          <Panel title="Runway configuration" description="As published on FAA NAS Status (informational).">
            {a.runway_config ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-[11px] text-ap-text-3">Arrivals</dt><dd className="font-mono">{a.runway_config.arrival_runway_config ?? "—"}</dd></div>
                <div><dt className="text-[11px] text-ap-text-3">Departures</dt><dd className="font-mono">{a.runway_config.departure_runway_config ?? "—"}</dd></div>
                <div><dt className="text-[11px] text-ap-text-3">Arrival rate</dt><dd className="tabular">{a.runway_config.arrival_rate ?? "—"} / hr</dd></div>
                <div><dt className="text-[11px] text-ap-text-3">As of</dt><dd className="tabular text-xs">{formatUtc(a.runway_config.source_timestamp)}</dd></div>
              </dl>
            ) : (
              <p className="text-sm text-ap-text-3">FAA has not published a configuration for this airport.</p>
            )}
          </Panel>
        </div>
      </div>

      <Panel
        className="mt-4"
        title="Observation history"
        description="Every stored METAR/SPECI for the selected window. Gaps mean no report was issued or ingested."
        actions={
          <ToggleGroup type="single" size="sm" value={String(hours)} onValueChange={(v) => v && setHours(Number(v))} aria-label="History window">
            {[12, 24, 72, 168].map((h) => (
              <ToggleGroupItem key={h} value={String(h)} className="px-2.5 text-xs">{h < 72 ? `${h}h` : `${h / 24}d`}</ToggleGroupItem>
            ))}
          </ToggleGroup>
        }
      >
        {weather.isError ? (
          <ErrorState error={weather.error} onRetry={() => weather.refetch()} />
        ) : !weather.data ? (
          <PanelSkeleton className="border-0 p-0 shadow-none" lines={4} />
        ) : weather.data.data.observations.length < 2 ? (
          <EmptyState title="Not enough history yet">
            AeroPulse has stored {weather.data.data.observations.length} observation(s) for this window. Trends appear as history accumulates.
          </EmptyState>
        ) : (
          <ObservationCharts observations={weather.data.data.observations} />
        )}
      </Panel>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="Terminal forecast (TAF)" description="Forecast issued by the National Weather Service — not an observation.">
          {a.forecast ? <TafTimeline forecast={a.forecast} timeZone={a.timezone} /> : <EmptyState title="No TAF stored">This station has no current TAF in AeroPulse.</EmptyState>}
        </Panel>
        <Panel title={`FAA advisories (${a.active_advisory_list.length} active)`} description="Reported by FAA NAS Status. Absence means nothing is reported, not that operations are verified normal.">
          <div className="space-y-2">
            {a.active_advisory_list.length === 0 && <p className="text-sm text-ap-text-2">No active FAA advisories reported for {a.iata_code}.</p>}
            {a.active_advisory_list.map((adv) => (
              <AdvisoryCard key={adv.id} advisory={adv} />
            ))}
            {pastAdvisories.length > 0 && (
              <details className="pt-2">
                <summary className="cursor-pointer text-xs text-ap-text-2 hover:text-ap-text">Cleared advisories ({pastAdvisories.length})</summary>
                <div className="mt-2 space-y-2">
                  {pastAdvisories.map((adv) => (
                    <AdvisoryCard key={adv.id} advisory={adv} />
                  ))}
                </div>
              </details>
            )}
          </div>
        </Panel>
      </div>
      <div className="mt-4 flex justify-end">
        <Button variant="outline" size="sm" asChild>
          <Link href={`/events?airport=${a.iata_code}`}>View {a.iata_code} event history</Link>
        </Button>
      </div>
    </PageContainer>
  );
}
