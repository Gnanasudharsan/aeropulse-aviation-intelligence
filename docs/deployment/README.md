# Deployment

See [hosting-evaluation.md](hosting-evaluation.md) for the options considered. The zero-cost
production topology is:

```mermaid
flowchart LR
  U[Browser] -->|HTTPS| V[Vercel · Next.js]
  U -->|HTTPS, CORS allow-list| R[Render free · FastAPI container]
  R -->|TLS| N[(Neon PostgreSQL free)]
  G[GitHub Actions cron */5] -->|POST /api/v1/admin/ingest/* · bearer token| R
  R -->|polls| FAA[FAA NAS Status] & AWC[NOAA AWC]
```

## 1. Database (Neon)

1. Create a free Neon project (PostgreSQL 16) and copy the **pooled** connection string.
2. TimescaleDB is not available on Neon; migration `0002` detects this and skips the
   hypertable (ADR-004). Everything else is identical.
3. Optional historical load (from a machine with the repo):
   `DATABASE_URL=… uv run --project services/api --group pipeline python pipelines/historical/bts_pipeline.py --start 2025-09 --end 2026-08 --delete-raw`
   (≈ 40 MB for 12 months of aggregates; stay within the free storage quota).

## 2. API (Render)

1. New → Blueprint → select this repository (`render.yaml`).
2. Set `DATABASE_URL` (Neon) and `CORS_ALLOW_ORIGINS` (the Vercel URL). Render generates
   `INGEST_TRIGGER_TOKEN`.
3. The container runs migrations and the airport seed on start, then serves on `$PORT`.
4. Check `https://<api>/api/v1/health` → `{"status":"ok","database":"ok"}`.

## 3. Web (Vercel)

```bash
cd apps/web
vercel link                                   # project root = apps/web
vercel env add NEXT_PUBLIC_API_BASE_URL production   # https://<api>.onrender.com
vercel env add NEXT_PUBLIC_POWERBI_REPORT_URL production   # optional, after publishing
vercel deploy --prod
```

## 4. Scheduled ingestion (GitHub Actions)

Repository → Settings → Secrets → Actions:

* `AEROPULSE_API_URL` = `https://<api>.onrender.com`
* `AEROPULSE_INGEST_TOKEN` = Render's generated `INGEST_TRIGGER_TOKEN`

`.github/workflows/ingest.yml` then runs every 5 minutes (FAA each run; METAR + risk every
10 min; TAF every 30 min). GitHub cron is best-effort; delays surface as `delayed`/`stale`
freshness, never as fabricated "live" data.

## Local / self-hosted (Docker Compose)

```bash
cp .env.example .env
docker compose up -d --build            # db, migrate, api (:8000), worker
docker compose --profile web up -d web  # optional production web container (:3000)
```

The worker container runs the APScheduler jobs (FAA 5 min, METAR 10 min, TAF 30 min, risk
10 min, bronze purge daily).

## Operations

* **Health:** `/api/v1/health` (liveness + DB), `/api/v1/status` (source health, last runs,
  data-quality checks).
* **Logs:** JSON lines (structlog) with request id, path, status and latency; secrets are
  redacted by key.
* **Error monitoring readiness:** logs are structured for any collector; the API never
  returns stack traces (structured `internal_error`).
* **Rate limiting:** per-IP, in-process (single instance). Behind multiple instances, move
  it to the edge.
