"use client";

import { keepPreviousData, useQuery as useTanstackQuery, type UseQueryOptions, type UseQueryResult } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { z } from "zod";

import { apiGet } from "./client";
import {
  AdvisoryDetail,
  Advisory,
  Analytics,
  AirportRisk,
  RiskOverview,
  AirportDetail,
  AirportSummary,
  AirportWeather,
  OperationalEvent,
  OperationsSummary,
  SourceFreshness,
  SystemStatus,
  WeatherOverview,
  WeatherTrendSeries,
} from "./schemas";

const noop = () => () => {};
/** False during server render and hydration, true afterwards. */
export function useHydrated(): boolean {
  return useSyncExternalStore(noop, () => true, () => false);
}

/**
 * useQuery that reports "pending" until hydration completes. Data that arrives before a
 * component hydrates would otherwise make client markup differ from the server shell.
 */
function useQuery<TData>(options: UseQueryOptions<TData>): UseQueryResult<TData> {
  const result = useTanstackQuery(options);
  const hydrated = useHydrated();
  if (hydrated) return result;
  return { ...result, data: undefined, isPending: true, isError: false, isSuccess: false, status: "pending", error: null } as unknown as UseQueryResult<TData>;
}

/** Operational data refreshes every 30 s against our own API (never upstream). */
export const LIVE_REFRESH_MS = 30_000;
const SLOW_REFRESH_MS = 60_000;

export function useOperationsSummary() {
  return useQuery({
    queryKey: ["operations", "summary"],
    queryFn: ({ signal }) => apiGet("/api/v1/operations/summary", OperationsSummary, undefined, signal),
    refetchInterval: LIVE_REFRESH_MS,
  });
}

export function useAirports() {
  return useQuery({
    queryKey: ["airports"],
    queryFn: ({ signal }) => apiGet("/api/v1/airports", z.array(AirportSummary), undefined, signal),
    refetchInterval: LIVE_REFRESH_MS,
  });
}

export function useAirport(code: string) {
  return useQuery({
    queryKey: ["airport", code],
    queryFn: ({ signal }) => apiGet(`/api/v1/airports/${encodeURIComponent(code)}`, AirportDetail, undefined, signal),
    refetchInterval: LIVE_REFRESH_MS,
    retry: (count, err) => (err as { status?: number }).status !== 404 && count < 2,
  });
}

export function useAirportWeather(code: string, hours: number) {
  return useQuery({
    queryKey: ["airport", code, "weather", hours],
    queryFn: ({ signal }) =>
      apiGet(`/api/v1/airports/${encodeURIComponent(code)}/weather`, AirportWeather, { hours }, signal),
    refetchInterval: SLOW_REFRESH_MS,
    placeholderData: keepPreviousData,
  });
}

export function useAirportAdvisories(code: string) {
  return useQuery({
    queryKey: ["airport", code, "advisories"],
    queryFn: ({ signal }) =>
      apiGet(`/api/v1/airports/${encodeURIComponent(code)}/advisories`, z.array(Advisory), { state: "all" }, signal),
    refetchInterval: SLOW_REFRESH_MS,
  });
}

export function useWeatherOverview() {
  return useQuery({
    queryKey: ["weather", "overview"],
    queryFn: ({ signal }) => apiGet("/api/v1/weather/overview", WeatherOverview, undefined, signal),
    refetchInterval: SLOW_REFRESH_MS,
  });
}

export function useWeatherTrends(airports: string[], hours: number) {
  return useQuery({
    queryKey: ["weather", "trends", airports.join(","), hours],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/weather/trends", z.array(WeatherTrendSeries), { airports: airports.join(","), hours }, signal),
    enabled: airports.length > 0,
    refetchInterval: SLOW_REFRESH_MS,
    placeholderData: keepPreviousData,
  });
}

export function useFreshness() {
  return useQuery({
    queryKey: ["freshness"],
    queryFn: ({ signal }) => apiGet("/api/v1/data-freshness", z.array(SourceFreshness), undefined, signal),
    refetchInterval: LIVE_REFRESH_MS,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: ({ signal }) => apiGet("/api/v1/status", SystemStatus, undefined, signal),
    refetchInterval: LIVE_REFRESH_MS,
  });
}

export interface EventFilters {
  airport?: string;
  type?: string[];
  event_type?: string[];
  since?: string;
  until?: string;
  sort?: "newest" | "oldest";
  page: number;
  page_size: number;
}

export function useEvents(filters: EventFilters) {
  return useQuery({
    queryKey: ["events", filters],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/operations/events", z.array(OperationalEvent), { ...filters }, signal),
    refetchInterval: LIVE_REFRESH_MS,
    placeholderData: keepPreviousData,
  });
}

export interface AdvisoryFilters {
  state: "active" | "inactive" | "all";
  airport?: string;
  type?: string[];
  q?: string;
  since?: string;
  sort?: "last_seen" | "first_seen" | "starts_at" | "airport";
  page: number;
  page_size: number;
}

export function useAdvisories(filters: AdvisoryFilters) {
  return useQuery({
    queryKey: ["advisories", filters],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/operations/advisories", z.array(Advisory), { ...filters }, signal),
    refetchInterval: LIVE_REFRESH_MS,
    placeholderData: keepPreviousData,
  });
}

export function useAdvisoryDetail(id: number | null) {
  return useQuery({
    queryKey: ["advisory", id],
    queryFn: ({ signal }) => apiGet(`/api/v1/operations/advisories/${id}`, AdvisoryDetail, undefined, signal),
    enabled: id !== null,
  });
}

export interface AnalyticsParams {
  start?: string;
  end?: string;
  direction: "arrival" | "departure";
}

/** Historical BTS analytics (monthly data — refreshed rarely). */
export function useAnalytics(params: AnalyticsParams, airport?: string) {
  const path = airport ? `/api/v1/airports/${encodeURIComponent(airport)}/history` : "/api/v1/analytics/overview";
  return useQuery({
    queryKey: ["analytics", airport ?? "network", params],
    queryFn: ({ signal }) => apiGet(path, Analytics, { ...params }, signal),
    staleTime: 30 * 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useRiskOverview() {
  return useQuery({
    queryKey: ["risk"],
    queryFn: ({ signal }) => apiGet("/api/v1/risk/airports", RiskOverview, undefined, signal),
    refetchInterval: LIVE_REFRESH_MS * 2,
  });
}

export function useAirportRisk(code: string | null, hours = 48) {
  return useQuery({
    queryKey: ["risk", code, hours],
    queryFn: ({ signal }) => apiGet(`/api/v1/risk/airports/${encodeURIComponent(code ?? "")}`, AirportRisk, { hours }, signal),
    enabled: code !== null,
    refetchInterval: LIVE_REFRESH_MS * 2,
  });
}
