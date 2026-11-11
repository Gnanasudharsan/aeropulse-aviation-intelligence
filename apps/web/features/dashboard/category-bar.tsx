import { CATEGORY_META, FLIGHT_CATEGORIES } from "@/lib/domain";

/** Segmented 100% bar of current flight categories, direct-labelled (no colour-only identity). */
export function CategoryBar({ counts, unknown }: { counts: Record<string, number>; unknown: number }) {
  const total = FLIGHT_CATEGORIES.reduce((s, c) => s + (counts[c] ?? 0), 0) + unknown;
  if (total === 0) return null;
  const segments = [
    ...FLIGHT_CATEGORIES.map((c) => ({ key: c, n: counts[c] ?? 0, color: CATEGORY_META[c].color, desc: CATEGORY_META[c].description })),
    { key: "No current obs", n: unknown, color: "var(--ap-unknown)", desc: "No METAR within the last 2 hours" },
  ].filter((s) => s.n > 0);
  return (
    <div className="space-y-3">
      <div className="flex h-2.5 gap-[2px] overflow-hidden rounded-full" role="img" aria-label={segments.map((s) => `${s.key}: ${s.n}`).join(", ")}>
        {segments.map((s) => (
          <div key={s.key} style={{ flexGrow: s.n, background: s.color }} title={`${s.key}: ${s.n} airports`} />
        ))}
      </div>
      <dl className="grid grid-cols-5 gap-2 text-center">
        {[...FLIGHT_CATEGORIES, "—" as const].map((c) => {
          const n = c === "—" ? unknown : (counts[c] ?? 0);
          return (
            <div key={c} title={c === "—" ? "No current observation" : CATEGORY_META[c].description}>
              <dt className="text-[11px] font-medium" style={{ color: c === "—" ? "var(--ap-unknown)" : CATEGORY_META[c].color }}>
                {c === "—" ? "N/A" : c}
              </dt>
              <dd className="tabular text-lg font-semibold text-ap-text">{n}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
