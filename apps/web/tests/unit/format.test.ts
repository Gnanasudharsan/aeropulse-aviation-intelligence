import { describe, expect, it } from "vitest";

import { cToF, formatUtc, num, relativeTime, visibility, wind } from "@/lib/format";

const NOW = Date.parse("2026-11-11T12:00:00Z");

describe("relativeTime", () => {
  it("handles missing timestamps", () => {
    expect(relativeTime(null, NOW)).toBe("never");
  });
  it("falls back to absolute UTC before the clock is available (prerender)", () => {
    expect(relativeTime("2026-11-11T11:00:00Z", null)).toBe("Nov 11, 11:00Z");
  });
  it.each([
    ["2026-11-11T11:59:50Z", "just now"],
    ["2026-11-11T11:55:00Z", "5 min ago"],
    ["2026-11-11T09:30:00Z", "2 h 30 min ago"],
    ["2026-11-09T12:00:00Z", "2 d ago"],
    ["2026-11-11T12:10:00Z", "in 10 min"],
  ])("%s -> %s", (iso, expected) => {
    expect(relativeTime(iso, NOW)).toBe(expected);
  });
});

describe("formatters", () => {
  it("formats UTC with a Z suffix", () => {
    expect(formatUtc("2026-11-11T04:05:00Z")).toBe("Nov 11, 04:05Z");
    expect(formatUtc(null)).toBe("—");
  });
  it("formats visibility including lower bounds", () => {
    expect(visibility(10, "10+", true)).toBe("≥ 10 SM");
    expect(visibility(0.5, "1/2", false)).toBe("0.50 SM");
    expect(visibility(null, null, false)).toBe("—");
  });
  it("formats wind", () => {
    expect(wind(260, false, 10, null)).toBe("260° 10 kt");
    expect(wind(null, true, 5, 18)).toBe("VRB 5 kt G18");
    expect(wind(0, false, 0, null)).toBe("Calm");
    expect(wind(null, false, null, null)).toBe("—");
  });
  it("never renders NaN", () => {
    expect(num(null)).toBe("—");
    expect(num(Number.NaN)).toBe("—");
    expect(num(1234.5, 1, " ft")).toBe("1,234.5 ft");
    expect(cToF(null)).toBeNull();
    expect(cToF(0)).toBe(32);
  });
});
