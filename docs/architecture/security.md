# Security review

Scope: API, ingestion, web app, CI/CD, deployment configuration. Reviewed 2026-11-11.

| Area | Control | Where |
|---|---|---|
| Secrets | `.env` git-ignored; only `.env.example` committed; gitleaks scan in CI; Render generates the ingestion token; no secrets in API responses; log processor redacts `authorization`, `password`, `token`, `secret`, `database_url` keys | `.gitignore`, `ci.yml`, `app/core/logging.py` |
| SQL injection | All values bound as parameters (SQLAlchemy Core/ORM, `text()` with binds). f-strings only interpolate internal constants (column lists, a fixed `AND airport_iata = :ap` clause) — never request input. Query parameters are validated (`Literal`, regex, ranges) before use | `app/repositories`, `app/api/v1/*` |
| XML parsing | Documents declaring entities are rejected before parsing (no entity expansion / XXE); only the expected root element is accepted | `app/ingestion/faa.py` |
| Admin endpoint | `POST /api/v1/admin/ingest/{job}` returns 404 unless `INGEST_TRIGGER_TOKEN` is set; constant-time bearer comparison (`hmac.compare_digest`) | `app/api/v1/system.py` |
| CORS | Explicit origin allow-list, `GET` only, no credentials | `app/main.py` |
| Abuse | Per-client fixed-window rate limit (default 120/min, `/health` exempt), `429` with `Retry-After`; `FORWARDED_ALLOW_IPS` set on Render so client IPs are real | `app/core/ratelimit.py`, `render.yaml` |
| Error handling | Structured errors only; DB failures return `503 database_unavailable` without connection details; no stack traces | `app/main.py` (tested) |
| Headers | API: `X-Content-Type-Options`, `Referrer-Policy`; web (Vercel): `X-Frame-Options: DENY`, `Permissions-Policy`, `nosniff` | `app/main.py`, `apps/web/vercel.json` |
| Embeds | Power BI iframe only for `https://*.powerbi.com` URLs; `referrerPolicy=no-referrer` | `features/analytics/powerbi-panel.tsx` |
| Map popups | Airport names are HTML-escaped before insertion into MapLibre popups | `components/map/airport-map.tsx` |
| Containers | Non-root users in API and web images; `--frozen` dependency installs; health checks | `Dockerfile`s |
| Dependencies | `pip-audit` (strict) and `npm audit --omit=dev --audit-level=high` in CI; Dependabot weekly | `ci.yml`, `dependabot.yml` |
| Upstream etiquette | Descriptive `User-Agent`, bounded retries with backoff, `Retry-After` honoured, polling well below documented limits | `app/ingestion/http.py` |

Results at review time: `pip-audit` — no known vulnerabilities; `npm audit --omit=dev` — 0
vulnerabilities (after moving the `shadcn` CLI, which pulled vulnerable transitive build
tools, to devDependencies).

Accepted risks: the rate limiter is per process (single instance); the FAA JSON endpoint is
unversioned (mitigated by the XML fallback and parse-failure data-quality checks).
