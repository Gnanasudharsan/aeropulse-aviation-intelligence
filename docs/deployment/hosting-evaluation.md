# Hosting evaluation

Goal: public website with near-real-time data at (ideally) zero recurring cost, with no
paid resources created without explicit owner approval.

| Component | Option | Free tier reality (as evaluated Nov 2026) | Verdict |
|---|---|---|---|
| Frontend | **Vercel Hobby** | Free for non-commercial; Next.js native; CLI already authenticated on dev machine. | **Selected** |
| Frontend | Netlify / Cloudflare Pages | Viable; weaker Next.js App Router parity. | Alternative |
| API | Render free web service | Free, but spins down after ~15 min idle (cold start 30–60 s); no always-on worker on free plan. | Viable for API only |
| API | Fly.io | No free allowance for new orgs; pay-as-you-go. | Requires approval |
| API | Railway | Trial credit, then paid. | Requires approval |
| API | Koyeb | One small free instance; availability varies by region. | Alternative |
| Database | **Neon** free | Serverless Postgres, ~0.5 GB storage, autosuspend; **no TimescaleDB**. | Selected for prod (schema degrades gracefully, ADR-004) |
| Database | Supabase free | 500 MB, pauses after 7 days inactivity; TimescaleDB deprecated on PG17. | Alternative |
| Database | Timescale Cloud | 30-day trial, then paid. | Requires approval |
| Scheduler | **GitHub Actions cron** | Free for public repos; schedules are best-effort and can be delayed 5–20 min under load. | Selected for prod triggers |
| Scheduler | Always-on worker | Requires paid compute on most hosts. | Local/Docker only unless approved |

## Selected production topology (zero cost)

> **Update (deployed):** the API runs as a Vercel Python serverless function and the
> database is Neon via the Vercel Marketplace, so a single already-authenticated account
> hosts everything; scheduling uses GitHub Actions calling the secret-free
> `/api/v1/ingest/tick` endpoint. The Render blueprint below remains a working alternative.

Original plan:

```
Vercel (Next.js) ──HTTPS──> Render free (FastAPI) ──> Neon Postgres (free)
                                    ▲
GitHub Actions cron (*/5) ──POST /api/v1/admin/ingest/{job} (bearer token)
```

Honest limitations of the free topology:

* GitHub Actions cron is best-effort; ingestion may lag the 5-minute target. The
  freshness model surfaces this as `delayed`/`stale` rather than hiding it.
* Render free instances cold-start; the first request after idle is slow. The web app
  shows skeletons and retries rather than errors.
* Neon storage limits require the retention policy in `docs/architecture/database.md#retention`.

Deployment is performed only after the repository owner approves account usage for
Render and Neon (both require sign-in with the owner's account).
