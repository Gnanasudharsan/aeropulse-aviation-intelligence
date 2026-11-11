import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { ApiError, apiGet, buildUrl } from "@/lib/api/client";
import { AirportSummary, OperationsSummary } from "@/lib/api/schemas";

const meta = { generated_at: "2026-11-11T04:00:00Z" };

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("buildUrl", () => {
  it("drops empty params and repeats arrays", () => {
    const url = new URL(buildUrl("/api/v1/operations/events", { airport: "JFK", type: ["ground_stop", "deicing"], q: "", page: 2, x: undefined }));
    expect(url.pathname).toBe("/api/v1/operations/events");
    expect(url.searchParams.getAll("type")).toEqual(["ground_stop", "deicing"]);
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.has("q")).toBe(false);
  });
});

describe("apiGet", () => {
  it("validates enveloped responses", async () => {
    const summary = {
      monitored_airports: 50, airports_with_active_advisories: 4, airports_with_disruptions: 0,
      active_ground_stops: 0, active_ground_delay_programs: 0, active_full_closures: 0,
      active_reported_delays: 0, active_partial_closures: 3,
      status_counts: { normal: 48, weather: 2 }, flight_categories: [{ category: "VFR", airports: 48 }],
      changes_last_hour: 0, recent_changes: [], faa_health: "healthy", weather_health: "healthy",
      faa_last_success_at: "2026-11-11T04:00:00Z", weather_last_success_at: null, latest_observation_at: null,
    };
    mockFetch({ data: summary, meta });
    const res = await apiGet("/api/v1/operations/summary", OperationsSummary);
    expect(res.data.monitored_airports).toBe(50);
  });

  it("rejects responses that drift from the contract", async () => {
    mockFetch({ data: [{ iata_code: "JFK" }], meta });
    await expect(apiGet("/api/v1/airports", z.array(AirportSummary))).rejects.toMatchObject({ code: "contract_mismatch" });
  });

  it("surfaces structured API errors", async () => {
    mockFetch({ error: { code: "not_found", message: "Airport 'XXX' is not monitored", details: null } }, 404);
    const err = await apiGet("/api/v1/airports/XXX", AirportSummary).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, code: "not_found" });
  });

  it("maps network failures to network_error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(apiGet("/api/v1/health", z.unknown())).rejects.toMatchObject({ code: "network_error", status: null });
  });
});
