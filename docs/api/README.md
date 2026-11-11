# AeroPulse API (v1)

Interactive docs: `GET /api/docs` (Swagger UI) and `/api/redoc`. The machine-readable
contract is committed at [`openapi.json`](openapi.json) and regenerated with:

```bash
cd services/api && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=1))" > ../../docs/api/openapi.json
```

## Conventions

* JSON envelope: `{"data": …, "meta": {"generated_at": …, "page"?, "page_size"?, "total"?, "total_pages"?}}`
* Errors: `{"error": {"code": "not_found" | "validation_error" | "rate_limited" | "database_unavailable" | …, "message": "…", "details": …}}`
* Timestamps: ISO-8601 UTC. Every operational record carries its own clock
  (`observed_at`, `source_published_at`, `ingested_at`, `first_seen_at`/`last_seen_at`).
* Caching: operational endpoints send `Cache-Control: public, max-age=15–60`.
* Rate limit: `RATE_LIMIT_PER_MINUTE` per client IP (default 120); `/health` is exempt.
* CORS: only origins in `CORS_ALLOW_ORIGINS`; `GET` only.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness + DB connectivity (`503` when the DB is unreachable). |
| GET | `/api/v1/status` | Overall live-source health, per-source freshness, last 15 ingestion runs, latest data-quality checks. |
| GET | `/api/v1/data-freshness` | Per-source health (`healthy`/`delayed`/`stale`/`unavailable`), thresholds and known limitations. |
| GET | `/api/v1/airports` | 50 monitored airports with status, weather risk and latest METAR fields. Filters: `q`, `status[]`, `flight_category[]`, `state`. |
| GET | `/api/v1/airports/{code}` | Detail by IATA or ICAO: latest METAR, risk factors, active advisories, latest TAF, runway configuration. |
| GET | `/api/v1/airports/{code}/weather?hours=24` | Observation history (≤168 h), hourly aggregates, latest TAF with periods. |
| GET | `/api/v1/airports/{code}/advisories?state=all` | FAA advisories for the airport (`active`/`inactive`/`all`). |
| GET | `/api/v1/operations/summary` | Command-center counters, status & flight-category distribution, changes in the last hour. |
| GET | `/api/v1/operations/advisories` | Paginated advisory search: `state`, `airport`, `type[]`, `since`, `until`, `q`, `sort`. |
| GET | `/api/v1/operations/advisories/{id}` | Advisory with its full lifecycle timeline and source link. |
| GET | `/api/v1/operations/events` | Paginated change log (`created`/`updated`/`cleared`/`reopened`); `format=csv` exports up to 10 000 rows. |
| GET | `/api/v1/weather/overview` | National observed-weather picture, extremes, advisory/IFR co-occurrence. |
| GET | `/api/v1/weather/trends?airports=JFK,ORD&hours=48` | Hourly series for up to 8 airports. |
| POST | `/api/v1/admin/ingest/{faa|metar|taf|all}` | Runs ingestion now. Requires `Authorization: Bearer $INGEST_TRIGGER_TOKEN`; returns 404 when no token is configured. |

Historical (`/airports/{code}/history`, `/analytics/overview`) and risk endpoints are
added with their corresponding phases and documented here when implemented.
