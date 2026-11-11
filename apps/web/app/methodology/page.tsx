import type { Metadata } from "next";

import { CategoryBadge, StatusBadge } from "@/components/data/badges";
import { PageContainer, PageHeader, Panel } from "@/components/layout/page";
import { SystemHealth } from "@/features/methodology/system-health";
import { CATEGORY_META, FLIGHT_CATEGORIES, STATUS_META, STATUS_ORDER } from "@/lib/domain";

export const metadata: Metadata = {
  title: "Methodology",
  description: "Data sources, freshness thresholds, and exact metric definitions used by AeroPulse.",
};

const DEFINITIONS: [string, string][] = [
  ["Advisory", "Any FAA NAS Status airport event: ground stop, ground delay program, airport closure, closure NOTAM, arrival/departure delay, or de-icing. Runway configuration is informational and not an advisory."],
  ["Active advisory", "Present in the most recent successful FAA poll and not past its published end time. An advisory that disappears from the feed is marked cleared at the first poll in which it is absent."],
  ["Ground stop", "An FAA-reported ground stop. Never inferred from weather or any other signal."],
  ["Ground delay program", "An FAA-reported GDP; the average delay shown is the FAA-reported value."],
  ["Closure scope", "Full = closed to all operations. Daily window = closed only inside a recurring UTC window (e.g. a curfew) and counted as a closure only inside it. Partial = closed to some operations only (e.g. transient GA) — displayed but never counted as a closure."],
  ["Reported delay", "An FAA arrival/departure delay entry with its reported range/average and trend."],
  ["Operational disruption", "An airport with an active ground stop, ground delay program, full closure, or reported arrival/departure delay."],
  ["Observed weather risk", "Rule-based tier from the latest METAR: low (VFR, wind < 20 kt); elevated (MVFR or wind/gust ≥ 20 kt); high (IFR, gust ≥ 35 kt, thunderstorm or freezing precipitation); severe (LIFR). It describes conditions, not delays."],
  ["Fresh data", "The source is Healthy and the record's own observation is within its threshold (METARs: observed within the last 2 hours)."],
  ["Delay (historical)", "BTS definition: a flight arriving 15 or more minutes after its scheduled time. Cancelled and diverted flights are excluded from on-time denominators."],
  ["Cancellation (historical)", "BTS-reported cancelled flight; cancellation rate = cancelled ÷ scheduled flights."],
];

export default function MethodologyPage() {
  return (
    <PageContainer>
      <PageHeader
        eyebrow="Trust & transparency"
        title="Data sources, freshness and definitions"
        description="AeroPulse separates what was reported (FAA), what was observed (METAR), what was forecast (TAF), and what we derive. Every figure traces back to a stored source record."
      />
      <SystemHealth />

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel id="status" title="Airport status rules" description="Evaluated top-down; the first matching rule wins.">
          <ol className="space-y-3">
            {STATUS_ORDER.map((s, i) => (
              <li key={s} className="flex items-start gap-3 text-sm">
                <span className="tabular mt-0.5 w-4 text-xs text-ap-text-3">{i + 1}</span>
                <StatusBadge status={s} className="w-44 shrink-0 justify-start" />
                <span className="text-ap-text-2">{STATUS_META[s].description}</span>
              </li>
            ))}
          </ol>
          <p className="mt-4 text-xs leading-relaxed text-ap-text-3">
            &ldquo;No reported issues&rdquo; additionally requires the FAA feed to be Healthy or Delayed — when FAA data is not current, an airport is shown as Insufficient data rather than normal.
          </p>
        </Panel>
        <Panel title="Flight categories (FAA)" description="Supplied by AWC with each METAR; derived from ceiling and visibility only when absent (flagged).">
          <ul className="space-y-2 text-sm">
            {FLIGHT_CATEGORIES.map((c) => (
              <li key={c} className="flex items-center gap-3">
                <CategoryBadge category={c} className="w-14 justify-center" />
                <span className="text-ap-text-2">{CATEGORY_META[c].description}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs leading-relaxed text-ap-text-3">Ceiling = lowest broken (BKN), overcast (OVC) or obscured layer, or vertical visibility.</p>
        </Panel>
      </div>

      <Panel className="mt-4" title="Metric definitions">
        <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          {DEFINITIONS.map(([term, def]) => (
            <div key={term}>
              <dt className="text-sm font-medium text-ap-text">{term}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-ap-text-2">{def}</dd>
            </div>
          ))}
        </dl>
      </Panel>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Four clocks, never conflated">
          <ol className="list-decimal space-y-1.5 pl-4 text-sm text-ap-text-2">
            <li><strong className="text-ap-text">Observation time</strong> — when the METAR was taken or the FAA event starts.</li>
            <li><strong className="text-ap-text">Source publication time</strong> — AWC receipt time / FAA update time.</li>
            <li><strong className="text-ap-text">Ingestion time</strong> — when AeroPulse stored it.</li>
            <li><strong className="text-ap-text">Page refresh time</strong> — when your browser last fetched from our API (every 30 s).</li>
          </ol>
        </Panel>
        <Panel title="Known limitations">
          <ul className="list-disc space-y-1.5 pl-4 text-sm text-ap-text-2">
            <li>FAA NAS Status lists only airports with active events; absence ≠ verified normal.</li>
            <li>The FAA JSON endpoint is public but not a formally versioned API; an XML fallback is used if it fails.</li>
            <li>Routine METARs are hourly; refreshing the page does not create newer observations.</li>
            <li>No aircraft position data is used; the map shows airports, not flights.</li>
            <li>Historical analytics are monthly BTS data with a 2–3 month lag.</li>
          </ul>
        </Panel>
        <Panel title="Not for operational use">
          <p className="text-sm leading-relaxed text-ap-text-2">
            AeroPulse is an analytics product. It is not a substitute for official FAA, NWS, or airline information and must not be used for flight planning or dispatch decisions.
          </p>
        </Panel>
      </div>
    </PageContainer>
  );
}
