"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MlMap, Marker, Popup } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { AirportSummary } from "@/lib/api/schemas";
import { CATEGORY_HEX, HEX, STATUS_HEX, STATUS_META } from "@/lib/domain";
import { cn } from "@/lib/utils";

export type ColorMode = "status" | "category";

const CONUS: [[number, number], [number, number]] = [
  [-125.5, 23.5],
  [-66, 50],
];

function markerColor(a: AirportSummary, mode: ColorMode): string {
  if (mode === "category") return a.flight_category && !a.weather_is_stale ? CATEGORY_HEX[a.flight_category] : HEX.unknown;
  return STATUS_HEX[a.status];
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

function popupHtml(a: AirportSummary): string {
  const status = STATUS_META[a.status];
  const vis = a.visibility_sm === null ? "—" : `${a.visibility_sm} SM`;
  const wind = a.wind_speed_kt === null ? "—" : `${a.wind_speed_kt}${a.wind_gust_kt ? `G${a.wind_gust_kt}` : ""} kt`;
  return `
    <div style="padding:12px 14px;min-width:220px;font-family:var(--font-geist-sans)">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline">
        <strong style="font-size:15px;letter-spacing:-0.01em">${a.iata_code}</strong>
        <span style="font-size:11px;color:${STATUS_HEX[a.status]}">● ${escapeHtml(status.label)}</span>
      </div>
      <div style="font-size:12px;color:${HEX.text2};margin-top:2px">${escapeHtml(a.name)}</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px;font-size:11px;color:${HEX.text3}">
        <div>Category<div style="color:${HEX.text};font-size:13px;font-weight:600">${a.flight_category ?? "—"}</div></div>
        <div>Visibility<div style="color:${HEX.text};font-size:13px">${vis}</div></div>
        <div>Wind<div style="color:${HEX.text};font-size:13px">${wind}</div></div>
      </div>
      <div style="font-size:11px;color:${HEX.text3};margin-top:8px">${a.active_advisories} active FAA advisor${a.active_advisories === 1 ? "y" : "ies"}${a.weather_is_stale ? " · weather stale" : ""}</div>
    </div>`;
}

export function AirportMap({
  airports,
  colorMode = "status",
  selected,
  onSelect,
  className,
  interactive = true,
}: {
  airports: AirportSummary[];
  colorMode?: ColorMode;
  selected?: string | null;
  onSelect?: (code: string) => void;
  className?: string;
  interactive?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const libRef = useRef<typeof import("maplibre-gl") | null>(null);
  const markers = useRef<Map<string, { marker: Marker; el: HTMLButtonElement }>>(new Map());
  const popupRef = useRef<Popup | null>(null);
  const onSelectRef = useRef(onSelect);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const lib = await import("maplibre-gl");
        if (cancelled || !container.current) return;
        lib.setWorkerUrl("/vendor/maplibre-gl-worker.mjs");
        libRef.current = lib;
        const map = new lib.Map({
          container: container.current,
          bounds: CONUS,
          fitBoundsOptions: { padding: 24 },
          attributionControl: { compact: true, customAttribution: "Boundaries: U.S. Census Bureau, Natural Earth" },
          interactive,
          dragRotate: false,
          pitchWithRotate: false,
          minZoom: 1.5,
          maxZoom: 9,
          style: {
            version: 8,
            sources: {
              land: { type: "geojson", data: "/geo/world-land.json" },
              nation: { type: "geojson", data: "/geo/us-nation.json" },
              states: { type: "geojson", data: "/geo/us-state-lines.json" },
            },
            layers: [
              { id: "bg", type: "background", paint: { "background-color": "#070d18" } },
              { id: "land", type: "fill", source: "land", paint: { "fill-color": "#0d1626" } },
              { id: "nation", type: "fill", source: "nation", paint: { "fill-color": "#12203a" } },
              { id: "nation-outline", type: "line", source: "nation", paint: { "line-color": "rgba(62,212,232,0.35)", "line-width": 1 } },
              { id: "states", type: "line", source: "states", paint: { "line-color": "rgba(168,190,211,0.16)", "line-width": 0.7 } },
            ],
          },
        });
        if (interactive) map.addControl(new lib.NavigationControl({ showCompass: false }), "bottom-right");
        map.scrollZoom.setWheelZoomRate(1 / 600);
        mapRef.current = map;
        // DOM markers don't depend on the style finishing loading.
        setReady(true);
      } catch {
        setFailed(true);
      }
    })();
    const markerMap = markers.current;
    return () => {
      cancelled = true;
      markerMap.forEach(({ marker }) => marker.remove());
      markerMap.clear();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [interactive]);

  // Sync markers with data.
  useEffect(() => {
    const map = mapRef.current;
    const lib = libRef.current;
    if (!ready || !map || !lib) return;
    const seen = new Set<string>();
    for (const a of airports) {
      seen.add(a.iata_code);
      const color = markerColor(a, colorMode);
      let entry = markers.current.get(a.iata_code);
      if (!entry) {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "ap-marker";
        el.innerHTML = `<span class="ap-marker-ring"></span><span class="ap-marker-dot"></span><span class="ap-marker-label">${a.iata_code}</span>`;
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          onSelectRef.current?.(a.iata_code);
        });
        const show = () => {
          popupRef.current?.remove();
          const current = markers.current.get(a.iata_code);
          const data = (current?.el as HTMLButtonElement & { _airport?: AirportSummary })._airport ?? a;
          popupRef.current = new lib.Popup({ closeButton: false, closeOnClick: false, offset: 14, maxWidth: "280px" })
            .setLngLat([a.longitude, a.latitude])
            .setHTML(popupHtml(data))
            .addTo(map);
        };
        const hide = () => popupRef.current?.remove();
        el.addEventListener("mouseenter", show);
        el.addEventListener("focus", show);
        el.addEventListener("mouseleave", hide);
        el.addEventListener("blur", hide);
        const marker = new lib.Marker({ element: el }).setLngLat([a.longitude, a.latitude]).addTo(map);
        entry = { marker, el };
        markers.current.set(a.iata_code, entry);
      }
      const el = entry.el as HTMLButtonElement & { _airport?: AirportSummary };
      el._airport = a;
      el.style.setProperty("--c", color);
      el.dataset.status = a.status;
      el.dataset.emphasis = String(a.status === "critical" || a.status === "warning" || a.status === "weather");
      el.dataset.selected = String(selected === a.iata_code);
      el.setAttribute(
        "aria-label",
        `${a.iata_code} ${a.name}: ${STATUS_META[a.status].label}${a.flight_category ? `, ${a.flight_category}` : ""}`,
      );
    }
    for (const [code, { marker }] of markers.current) {
      if (!seen.has(code)) {
        marker.remove();
        markers.current.delete(code);
      }
    }
  }, [airports, colorMode, ready, selected]);

  const flyTo = (target: "conus" | "hawaii") => {
    const map = mapRef.current;
    if (!map) return;
    if (target === "conus") map.fitBounds(CONUS, { padding: 24, duration: 900 });
    else map.flyTo({ center: [-157.9, 21.3], zoom: 6.5, duration: 900 });
  };

  return (
    <div className={cn("relative overflow-hidden rounded-xl bg-[#070d18]", className)}>
      <div ref={container} className="h-full w-full" />
      {!ready && !failed && (
        <div className="absolute inset-0 grid place-items-center text-xs text-ap-text-3">Loading map…</div>
      )}
      {failed && (
        <div className="absolute inset-0 grid place-items-center text-sm text-ap-text-2">
          The map could not be rendered (WebGL unavailable). Use the airport list instead.
        </div>
      )}
      {interactive && ready && (
        <div className="absolute left-3 top-3 flex gap-1 rounded-lg border border-ap-line bg-ap-bg/80 p-1 text-[11px] backdrop-blur">
          <button type="button" className="rounded px-2 py-1 text-ap-text-2 hover:bg-white/5 hover:text-ap-text" onClick={() => flyTo("conus")}>
            Contiguous U.S.
          </button>
          <button type="button" className="rounded px-2 py-1 text-ap-text-2 hover:bg-white/5 hover:text-ap-text" onClick={() => flyTo("hawaii")}>
            Hawaii
          </button>
        </div>
      )}
      <style>{`
        .ap-marker { width: 22px; height: 22px; display: grid; place-items: center; cursor: pointer; background: none; border: 0; padding: 0; }
        .ap-marker:focus-visible { outline: 2px solid ${HEX.accent}; outline-offset: 2px; border-radius: 999px; }
        .ap-marker-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--c); box-shadow: 0 0 0 2px #070d18, 0 0 10px var(--c); transition: transform .15s ease; }
        .ap-marker[data-emphasis="true"] .ap-marker-dot { width: 12px; height: 12px; }
        .ap-marker:hover .ap-marker-dot, .ap-marker[data-selected="true"] .ap-marker-dot { transform: scale(1.35); }
        .ap-marker-ring { position: absolute; inset: 2px; border-radius: 999px; border: 1.5px solid var(--c); opacity: 0; }
        .ap-marker[data-status="critical"] .ap-marker-ring { animation: ap-ping 2.2s cubic-bezier(0,0,.2,1) infinite; }
        .ap-marker[data-selected="true"] .ap-marker-ring { opacity: .9; animation: none; inset: -2px; }
        .ap-marker-label { position: absolute; left: 20px; top: 50%; transform: translateY(-50%); font: 600 10px/1 var(--font-geist-mono), monospace; color: ${HEX.text2}; letter-spacing: .04em; opacity: 0; pointer-events: none; text-shadow: 0 1px 3px #000; }
        .ap-marker[data-emphasis="true"] .ap-marker-label, .ap-marker:hover .ap-marker-label, .ap-marker:focus-visible .ap-marker-label, .ap-marker[data-selected="true"] .ap-marker-label { opacity: 1; color: ${HEX.text}; }
        @keyframes ap-ping { 0% { transform: scale(.6); opacity: .9 } 80%,100% { transform: scale(2.1); opacity: 0 } }
        @media (prefers-reduced-motion: reduce) { .ap-marker-ring { animation: none !important } }
      `}</style>
    </div>
  );
}
