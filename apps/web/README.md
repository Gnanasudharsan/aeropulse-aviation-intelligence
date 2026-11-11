# AeroPulse web

Next.js 16 (App Router, Cache Components) front end. See the repository root README for the
full architecture.

```bash
npm install
npm run dev          # http://localhost:3000 (expects the API on NEXT_PUBLIC_API_BASE_URL)
npm run typecheck && npm run lint && npm test
npm run build && npm run test:e2e   # Playwright smoke tests against `next start` on :3100
```

* `lib/api` — Zod contracts mirroring the FastAPI schemas, fetch client, TanStack Query hooks
  (30 s refresh against our API, never upstream).
* `features/*` — one folder per page; `components/*` — shared UI (shadcn/ui primitives in
  `components/ui`).
* Live data is fetched client-side; pages prerender a static shell. Clock reads use
  `hooks/use-now.ts` so prerendering never reads `Date.now()` during render.
* `scripts/build-geo.mjs` builds the public-domain basemap GeoJSON (U.S. Census via
  `us-atlas`, Natural Earth via `world-atlas`). `scripts/copy-maplibre-worker.mjs` serves
  MapLibre's worker as a static file (Turbopack cannot bundle it).
