import type { AirportStatus, SourceHealth, WeatherRisk } from "@/lib/api/schemas";
import { ADVISORY_LABELS, CATEGORY_META, HEALTH_META, RISK_META, STATUS_META } from "@/lib/domain";
import { cn } from "@/lib/utils";

const base =
  "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5 whitespace-nowrap";

function tint(color: string) {
  return {
    color,
    borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
    background: `color-mix(in srgb, ${color} 12%, transparent)`,
  };
}

export function StatusBadge({ status, className, compact }: { status: AirportStatus; className?: string; compact?: boolean }) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <span className={cn(base, className)} style={tint(meta.color)} title={meta.description}>
      <Icon className="size-3" aria-hidden />
      {compact ? meta.label.split(" ")[0] : meta.label}
    </span>
  );
}

export function CategoryBadge({ category, className }: { category: string | null; className?: string }) {
  if (!category) return <span className={cn(base, "border-ap-line text-ap-text-3", className)}>No obs</span>;
  const meta = CATEGORY_META[category];
  return (
    <span className={cn(base, "font-semibold tracking-wide", className)} style={tint(meta?.color ?? "var(--ap-text-3)")} title={meta?.description}>
      {category}
    </span>
  );
}

export function HealthBadge({ health, className }: { health: SourceHealth; className?: string }) {
  const meta = HEALTH_META[health];
  return (
    <span className={cn(base, className)} style={tint(meta.color)}>
      <span className="size-1.5 rounded-full" style={{ background: meta.color }} aria-hidden />
      {meta.label}
    </span>
  );
}

export function RiskBadge({ risk, className }: { risk: WeatherRisk; className?: string }) {
  const meta = RISK_META[risk];
  return (
    <span className={cn(base, className)} style={tint(meta.color)}>
      {meta.label} weather risk
    </span>
  );
}

export function AdvisoryTypeBadge({ type, className }: { type: string; className?: string }) {
  const crit = type === "ground_stop" || type === "ground_delay_program" || type === "airport_closure";
  const warn = type === "arrival_delay" || type === "departure_delay";
  const color = crit ? "var(--ap-crit)" : warn ? "var(--ap-warn)" : "var(--ap-text-2)";
  return (
    <span className={cn(base, className)} style={tint(color)}>
      {ADVISORY_LABELS[type] ?? type}
    </span>
  );
}
