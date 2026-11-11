import {
  ArrowRight,
  BarChart3,
  CloudSun,
  Database,
  Gauge,
  ListTree,
  Map,
  Radar,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { PageContainer } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { HeroMap, LiveStats } from "@/features/landing/live-hero";

const FEATURES = [
  { icon: Map, title: "National command center", body: "Every monitored airport on one map, coloured only by FAA-reported events and observed METAR conditions.", href: "/dashboard" },
  { icon: Radar, title: "Airport intelligence", body: "Decoded METARs, 7-day observation history, TAF timelines, runway configuration and advisory history per airport.", href: "/airports" },
  { icon: CloudSun, title: "Weather impact", body: "Flight-category distribution, visibility and wind comparisons, hourly trends and advisory co-occurrence.", href: "/weather" },
  { icon: ListTree, title: "Event explorer", body: "Full lifecycle of every FAA advisory — reported, updated, cleared — searchable and exportable to CSV.", href: "/events" },
  { icon: Gauge, title: "Freshness you can audit", body: "Live source health against documented thresholds, ingestion runs and data-quality checks.", href: "/methodology" },
  { icon: BarChart3, title: "Historical analytics", body: "BTS on-time performance modelled as a star schema for Power BI — delays, cancellations and causes.", href: "/analytics" },
];

const PIPELINE = [
  { icon: Radar, title: "Official sources", body: "FAA NAS Status · NOAA AWC METAR/TAF · BTS" },
  { icon: Workflow, title: "Scheduled ingestion", body: "5–30 min polling, retries, raw payloads kept" },
  { icon: ShieldCheck, title: "Validation", body: "Schema checks, dedup, quality results" },
  { icon: Database, title: "PostgreSQL", body: "Bronze → silver → gold, TimescaleDB" },
  { icon: Gauge, title: "Versioned API", body: "FastAPI, typed contracts, freshness" },
];

export default function LandingPage() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div className="ap-grid-bg absolute inset-0" aria-hidden />
        <div className="absolute left-1/2 top-[-200px] h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(62,212,232,0.14),transparent)]" aria-hidden />
        <PageContainer className="relative grid items-center gap-12 pb-16 pt-14 sm:pt-20 lg:grid-cols-[1.05fr_1fr]">
          <div className="space-y-7">
            <p className="inline-flex items-center gap-2 rounded-full border border-ap-line bg-ap-surface/60 px-3 py-1 text-xs text-ap-text-2">
              <span className="size-1.5 rounded-full bg-ap-ok shadow-[0_0_8px_var(--ap-ok)]" aria-hidden />
              Live FAA NAS Status + NOAA Aviation Weather data
            </p>
            <h1 className="text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-ap-text sm:text-5xl xl:text-6xl">
              Intelligence
              <br />
              <span className="bg-gradient-to-r from-ap-accent via-[#7fe3f0] to-ap-ok bg-clip-text text-transparent">in Motion.</span>
            </h1>
            <p className="max-w-xl text-base leading-relaxed text-ap-text-2 sm:text-lg">
              AeroPulse turns official U.S. aviation feeds into a real-time picture of operations at 50 major airports — what the FAA is reporting, what the weather is doing, what changed, and how fresh every number is.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button size="lg" asChild className="gap-2">
                <Link href="/dashboard">
                  Open Command Center <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/methodology">How the data works</Link>
              </Button>
            </div>
            <div className="border-t border-ap-line pt-6">
              <LiveStats />
            </div>
          </div>
          <HeroMap />
        </PageContainer>
      </section>

      <PageContainer className="py-16">
        <div className="mb-10 max-w-2xl space-y-3">
          <p className="ap-eyebrow">Product</p>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Operational awareness without guesswork</h2>
          <p className="text-ap-text-2">Reported events, observed weather, forecasts and model output are kept visibly separate — so a low-visibility morning is never mistaken for a ground stop.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <Link key={f.title} href={f.href} className="ap-panel group p-6 transition-transform hover:-translate-y-0.5">
              <f.icon className="size-5 text-ap-accent" aria-hidden />
              <h3 className="mt-4 font-semibold text-ap-text">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ap-text-2">{f.body}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-xs text-ap-accent opacity-0 transition-opacity group-hover:opacity-100">
                Explore <ArrowRight className="size-3" />
              </span>
            </Link>
          ))}
        </div>
      </PageContainer>

      <PageContainer className="pb-8">
        <div className="ap-panel overflow-hidden p-6 sm:p-10">
          <p className="ap-eyebrow">Architecture</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">From government feed to your screen</h2>
          <ol className="mt-8 grid gap-4 md:grid-cols-5">
            {PIPELINE.map((p, i) => (
              <li key={p.title} className="relative rounded-xl border border-ap-line bg-ap-bg/50 p-4">
                <span className="tabular absolute right-3 top-3 text-[10px] text-ap-text-3">0{i + 1}</span>
                <p.icon className="size-4 text-ap-accent" aria-hidden />
                <p className="mt-3 text-sm font-medium">{p.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-ap-text-3">{p.body}</p>
              </li>
            ))}
          </ol>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button variant="outline" asChild>
              <Link href="/about">Engineering overview</Link>
            </Button>
            <Button variant="ghost" asChild>
              <a href="https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence" target="_blank" rel="noreferrer">
                View source
              </a>
            </Button>
          </div>
        </div>
      </PageContainer>
    </>
  );
}
