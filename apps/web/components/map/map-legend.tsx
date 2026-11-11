import type { ColorMode } from "./airport-map";
import { CATEGORY_META, FLIGHT_CATEGORIES, STATUS_META, STATUS_ORDER } from "@/lib/domain";

export function MapLegend({ mode, counts }: { mode: ColorMode; counts?: Record<string, number> }) {
  const items =
    mode === "status"
      ? STATUS_ORDER.map((s) => ({ key: s, label: STATUS_META[s].label, color: STATUS_META[s].color, title: STATUS_META[s].description }))
      : [
          ...FLIGHT_CATEGORIES.map((c) => ({ key: c, label: c, color: CATEGORY_META[c].color, title: CATEGORY_META[c].description })),
          { key: "none", label: "No current obs", color: "var(--ap-unknown)", title: "No METAR in the last 2 hours" },
        ];
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-ap-text-2" aria-label="Map legend">
      {items.map((i) => (
        <li key={i.key} className="flex items-center gap-1.5" title={i.title}>
          <span className="size-2 rounded-full" style={{ background: i.color }} aria-hidden />
          {i.label}
          {counts && counts[i.key] !== undefined && <span className="tabular text-ap-text-3">{counts[i.key]}</span>}
        </li>
      ))}
    </ul>
  );
}
