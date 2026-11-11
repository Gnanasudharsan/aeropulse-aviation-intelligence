import type { Metadata } from "next";

import { PageContainer, PageHeader, Panel } from "@/components/layout/page";
import { API_BASE_URL, API_CONFIGURED } from "@/lib/api/client";

export const metadata: Metadata = {
  title: "About",
  description: "Product and engineering overview of AeroPulse.",
};

const STACK: [string, string[]][] = [
  ["Frontend", ["Next.js 16 (App Router, Cache Components)", "TypeScript", "Tailwind CSS 4 + shadcn/ui", "TanStack Query + Zod contracts", "MapLibre GL", "Apache ECharts", "Motion"]],
  ["Backend", ["Python 3.12 · FastAPI", "SQLAlchemy 2 · Alembic", "PostgreSQL 16 + TimescaleDB", "httpx async clients", "APScheduler worker", "structlog JSON logs"]],
  ["Data & BI", ["Bronze/silver/gold layers", "Data-quality checks per run", "BTS star schema", "Power BI semantic model + DAX"]],
  ["Quality & ops", ["pytest (unit + PostgreSQL integration)", "Vitest + Testing Library", "Playwright smoke tests", "GitHub Actions CI", "Docker Compose"]],
];

const DECISIONS: [string, string][] = [
  ["Evidence-based status", "Map colours come only from FAA-reported events and observed METARs. Weather never implies a ground stop; model output lives in its own module."],
  ["Lightweight orchestration", "Three periodic HTTP jobs don't justify an Airflow cluster. A single APScheduler worker plus an auditable ingestion_runs table gives the needed observability; jobs are plain functions an orchestrator can wrap later."],
  ["FAA JSON primary, XML fallback", "The JSON feed carries stable event ids and ISO timestamps; the long-standing XML feed provides a publication timestamp and a fallback parser. Both raw payloads are retained."],
  ["Idempotent by construction", "Natural keys and ON CONFLICT upserts mean re-polling never duplicates observations; a 3-hour METAR look-back back-fills missed runs."],
  ["Honest freshness", "Health is computed from documented thresholds and surfaced everywhere. When a source stops, the last valid data stays visible — labelled stale."],
  ["Client-side live data", "Pages prerender a static shell; live data is fetched from our API every 30 s and validated with Zod before rendering."],
];

export default function AboutPage() {
  return (
    <PageContainer>
      <PageHeader
        eyebrow="About AeroPulse"
        title="A real data product, end to end"
        description="AeroPulse ingests official FAA and NOAA feeds, validates and stores them in PostgreSQL, and serves a versioned API to this web application — with historical BTS analytics modelled for Power BI."
      />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {STACK.map(([title, items]) => (
          <Panel key={title} title={title}>
            <ul className="space-y-1.5 text-sm text-ap-text-2">
              {items.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
      <Panel className="mt-4" title="Key engineering decisions">
        <dl className="grid gap-x-8 gap-y-5 md:grid-cols-2">
          {DECISIONS.map(([t, d]) => (
            <div key={t}>
              <dt className="font-medium text-ap-text">{t}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-ap-text-2">{d}</dd>
            </div>
          ))}
        </dl>
      </Panel>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Panel title="API">
          {API_CONFIGURED ? (
            <p className="text-sm text-ap-text-2">
              Interactive OpenAPI documentation:{" "}
              <a className="text-ap-accent hover:underline" href={`${API_BASE_URL}/api/docs`} target="_blank" rel="noreferrer">
                {API_BASE_URL}/api/docs
              </a>
            </p>
          ) : (
            <p className="text-sm text-ap-text-2">
              This deployment is not connected to a hosted API. Run the stack locally and open{" "}
              <code className="font-mono text-xs">http://localhost:8000/api/docs</code>, or see the committed{" "}
              <a className="text-ap-accent underline underline-offset-2" href="https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence/blob/main/docs/api/README.md" target="_blank" rel="noreferrer">
                API reference
              </a>
              .
            </p>
          )}
        </Panel>
        <Panel title="Source code">
          <p className="text-sm text-ap-text-2">
            <a className="text-ap-accent hover:underline" href="https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence" target="_blank" rel="noreferrer">
              github.com/Gnanasudharsan/aeropulse-aviation-intelligence
            </a>{" "}
            — architecture decision records, data-source verification log and metric definitions live in <code className="font-mono text-xs">docs/</code>.
          </p>
        </Panel>
      </div>
    </PageContainer>
  );
}
