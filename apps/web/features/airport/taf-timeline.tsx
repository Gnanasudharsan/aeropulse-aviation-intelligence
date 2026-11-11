"use client";

import type { Forecast } from "@/lib/api/schemas";
import { CATEGORY_META } from "@/lib/domain";
import { formatLocal, formatUtc } from "@/lib/format";

const CHANGE: Record<string, string> = {
  FM: "From",
  BECMG: "Becoming",
  TEMPO: "Temporarily",
  PROB: "Probability",
};

/** TAF as a horizontal timeline of forecast periods (forecast — not observation). */
export function TafTimeline({ forecast, timeZone }: { forecast: Forecast; timeZone: string }) {
  const start = Date.parse(forecast.valid_from);
  const end = Date.parse(forecast.valid_to);
  const span = Math.max(end - start, 1);
  const base = forecast.periods.filter((p) => !p.change_indicator || p.change_indicator === "FM");
  const overlays = forecast.periods.filter((p) => p.change_indicator && p.change_indicator !== "FM");
  const ticks = Array.from({ length: 5 }, (_, i) => new Date(start + (span * i) / 4).toISOString());

  const bar = (p: Forecast["periods"][number], i: number, overlay = false) => {
    const left = ((Date.parse(p.time_from) - start) / span) * 100;
    const width = ((Date.parse(p.time_to) - Date.parse(p.time_from)) / span) * 100;
    const color = p.flight_category ? CATEGORY_META[p.flight_category]?.color : "var(--ap-unknown)";
    const label = `${p.change_indicator ? `${CHANGE[p.change_indicator] ?? p.change_indicator}${p.probability ? ` ${p.probability}%` : ""} ` : ""}${formatUtc(p.time_from)}–${formatUtc(p.time_to)}: ${p.flight_category ?? "n/a"}, wind ${p.wind_speed_kt ?? "—"} kt${p.wind_gust_kt ? ` G${p.wind_gust_kt}` : ""}, vis ${p.visibility_text ?? "—"}${p.wx_string ? `, ${p.wx_string}` : ""}`;
    return (
      <div
        key={`${overlay ? "o" : "b"}${i}`}
        className="absolute flex items-center overflow-hidden rounded-[4px] px-1.5 text-[10px] font-semibold text-[#06101c]"
        style={{
          left: `${Math.max(left, 0)}%`,
          width: `calc(${Math.min(width, 100 - left)}% - 2px)`,
          top: overlay ? 30 : 0,
          height: overlay ? 18 : 26,
          background: overlay ? `repeating-linear-gradient(135deg, ${color} 0 6px, color-mix(in srgb, ${color} 55%, transparent) 6px 10px)` : color,
        }}
        title={label}
        role="listitem"
        aria-label={label}
      >
        <span className="truncate">{p.flight_category ?? "?"}{overlay && p.change_indicator ? ` ${p.change_indicator}` : ""}</span>
      </div>
    );
  };

  return (
    <div className="space-y-3">
      <div className="relative h-[52px]" role="list" aria-label="TAF forecast periods">
        {base.map((p, i) => bar(p, i))}
        {overlays.map((p, i) => bar(p, i, true))}
      </div>
      <div className="flex justify-between text-[10px] text-ap-text-3 tabular">
        {ticks.map((t) => (
          <span key={t}>{formatUtc(t)}</span>
        ))}
      </div>
      <p className="text-[11px] text-ap-text-3">
        Issued {formatUtc(forecast.issued_at)} ({formatLocal(forecast.issued_at, timeZone)}){forecast.is_amendment ? " · amended" : ""}. Solid bars are the prevailing forecast; hatched bars are TEMPO/BECMG/PROB groups.
      </p>
      <details className="text-xs">
        <summary className="cursor-pointer text-ap-text-2 hover:text-ap-text">Raw TAF</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-ap-bg/70 p-3 font-mono text-[11px] leading-relaxed text-ap-text-2">{forecast.raw_text}</pre>
      </details>
    </div>
  );
}
