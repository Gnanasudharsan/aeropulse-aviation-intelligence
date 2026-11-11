/**
 * Domain vocabulary shared across the UI. Colours reference CSS tokens only.
 * Status colours are always paired with an icon + text label (never colour alone).
 */
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  CloudFog,
  type LucideIcon,
} from "lucide-react";

import type { AirportStatus, SourceHealth, WeatherRisk } from "./api/schemas";

export const STATUS_META: Record<
  AirportStatus,
  { label: string; color: string; icon: LucideIcon; description: string }
> = {
  critical: {
    label: "FAA program / closure",
    color: "var(--ap-crit)",
    icon: AlertOctagon,
    description: "FAA-reported ground stop, ground delay program, or full closure",
  },
  warning: {
    label: "Reported delays",
    color: "var(--ap-warn)",
    icon: AlertTriangle,
    description: "FAA-reported arrival/departure delays",
  },
  weather: {
    label: "IFR / LIFR weather",
    color: "var(--ap-lifr)",
    icon: CloudFog,
    description: "Low ceilings or visibility observed — no FAA program reported",
  },
  normal: {
    label: "No reported issues",
    color: "var(--ap-ok)",
    icon: CheckCircle2,
    description: "No FAA advisories; current METAR is not IFR/LIFR",
  },
  unknown: {
    label: "Insufficient data",
    color: "var(--ap-unknown)",
    icon: CircleHelp,
    description: "No current observation or the FAA feed is not current",
  },
};

export const STATUS_ORDER: AirportStatus[] = ["critical", "warning", "weather", "normal", "unknown"];

export const HEALTH_META: Record<SourceHealth, { label: string; color: string }> = {
  healthy: { label: "Healthy", color: "var(--ap-ok)" },
  delayed: { label: "Delayed", color: "var(--ap-warn)" },
  stale: { label: "Stale", color: "var(--ap-crit)" },
  unavailable: { label: "Unavailable", color: "var(--ap-unknown)" },
};

export const FLIGHT_CATEGORIES = ["VFR", "MVFR", "IFR", "LIFR"] as const;

export const CATEGORY_META: Record<string, { color: string; description: string }> = {
  VFR: { color: "var(--ap-vfr)", description: "Ceiling > 3,000 ft and visibility > 5 SM" },
  MVFR: { color: "var(--ap-mvfr)", description: "Ceiling 1,000–3,000 ft or visibility 3–5 SM" },
  IFR: { color: "var(--ap-ifr)", description: "Ceiling 500–999 ft or visibility 1–<3 SM" },
  LIFR: { color: "var(--ap-lifr)", description: "Ceiling < 500 ft or visibility < 1 SM" },
};

export const RISK_META: Record<WeatherRisk, { label: string; color: string }> = {
  low: { label: "Low", color: "var(--ap-ok)" },
  elevated: { label: "Elevated", color: "var(--ap-warn)" },
  high: { label: "High", color: "var(--ap-crit)" },
  severe: { label: "Severe", color: "var(--ap-lifr)" },
  unknown: { label: "Unknown", color: "var(--ap-unknown)" },
};

export const ADVISORY_LABELS: Record<string, string> = {
  ground_stop: "Ground stop",
  ground_delay_program: "Ground delay program",
  airport_closure: "Airport closure",
  closure_notam: "Closure NOTAM",
  arrival_delay: "Arrival delay",
  departure_delay: "Departure delay",
  deicing: "De-icing",
};

export const SCOPE_LABELS: Record<string, string> = {
  full: "Full",
  partial: "Partial (some operations)",
  daily_window: "Daily window",
};

export const EVENT_LABELS: Record<string, string> = {
  created: "Reported",
  updated: "Updated",
  cleared: "Cleared",
  reopened: "Re-reported",
};

/** Raw hex for canvas renderers (ECharts / MapLibre) that cannot read CSS vars. */
export const HEX = {
  bg: "#0b1220",
  surface: "#16263e",
  surface2: "#1c3050",
  line: "rgba(168,190,211,0.12)",
  lineStrong: "rgba(168,190,211,0.22)",
  text: "#f3f8ff",
  text2: "#a8bed3",
  text3: "#7690aa",
  accent: "#3ed4e8",
  ok: "#49dbaa",
  warn: "#ffb454",
  crit: "#f27989",
  unknown: "#7690aa",
  vfr: "#49dbaa",
  mvfr: "#5b9cff",
  ifr: "#f27989",
  lifr: "#d77bea",
  series: ["#1a9db2", "#d9733f", "#9085e9", "#aa880a", "#d55181", "#4c9a2a"],
} as const;

export const STATUS_HEX: Record<AirportStatus, string> = {
  critical: HEX.crit,
  warning: HEX.warn,
  weather: HEX.lifr,
  normal: HEX.ok,
  unknown: HEX.unknown,
};

export const CATEGORY_HEX: Record<string, string> = {
  VFR: HEX.vfr,
  MVFR: HEX.mvfr,
  IFR: HEX.ifr,
  LIFR: HEX.lifr,
};
