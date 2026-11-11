/** Formatting helpers. All inputs are ISO-8601 UTC strings from the API. */

export function relativeTime(iso: string | null | undefined, now: number | null): string {
  if (!iso) return "never";
  if (now === null) return formatUtc(iso);
  const diff = Math.round((now - Date.parse(iso)) / 1000);
  const future = diff < 0;
  const s = Math.abs(diff);
  let text: string;
  if (s < 45) text = "just now";
  else if (s < 3600) text = `${Math.round(s / 60)} min`;
  else if (s < 86_400) text = `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min`;
  else text = `${Math.round(s / 86_400)} d`;
  if (text === "just now") return text;
  return future ? `in ${text}` : `${text} ago`;
}

const utcFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${utcFmt.format(new Date(iso))}Z`;
}

export function formatLocal(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
    timeZoneName: "short",
  }).format(new Date(iso));
}

export function hourLabel(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getUTCHours()).padStart(2, "0")}Z`;
}

export function num(value: number | null | undefined, digits = 0, suffix = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}${suffix}`;
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function visibility(sm: number | null, text: string | null, lowerBound: boolean): string {
  if (sm === null) return text ?? "—";
  return `${lowerBound ? "≥ " : ""}${sm % 1 === 0 ? sm : sm.toFixed(2)} SM`;
}

export function wind(dir: number | null, variable: boolean, speed: number | null, gust: number | null): string {
  if (speed === null) return "—";
  if (speed === 0) return "Calm";
  const d = variable ? "VRB" : dir !== null ? `${String(dir).padStart(3, "0")}°` : "—";
  return `${d} ${speed} kt${gust ? ` G${gust}` : ""}`;
}

export function cToF(c: number | null): number | null {
  return c === null ? null : Math.round((c * 9) / 5 + 32);
}
