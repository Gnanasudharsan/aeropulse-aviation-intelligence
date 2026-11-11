# Metric definitions

Exact, testable definitions used by the API, the web app and the Power BI model.
Live operational metrics and historical metrics are never mixed.

## Live operational (FAA NAS Status + NOAA AWC)

| Term | Definition |
|---|---|
| **Monitored airport** | One of the 50 airports in `airports` where `is_monitored = true`. |
| **Advisory** | Any FAA NAS Status airport event of type `ground_stop`, `ground_delay_program`, `airport_closure`, `closure_notam`, `arrival_delay`, `departure_delay`, `deicing`. Runway configuration is *not* an advisory. |
| **Active advisory** | An advisory that (a) appeared in the most recent *successful* FAA poll, and (b) whose `ends_at` is null or in the future. An advisory that disappears from the feed is marked `cleared_at = first poll in which it was absent`. |
| **Ground stop** | Advisory of type `ground_stop` as reported by FAA. Never inferred from weather. |
| **Ground delay program (GDP)** | Advisory of type `ground_delay_program` as reported by FAA; `avg_delay_minutes` is the FAA-reported average. |
| **Airport closure** | `airport_closure` = FAA-reported full closure. `closure_notam` = NOTAM closure that may be partial (e.g. to transient GA only); it is displayed but never counted as a full closure. |
| **Reported delay** | `arrival_delay`/`departure_delay` advisory with FAA-reported min/max/average minutes and trend. |
| **Operational disruption (airport)** | Airport has ≥ 1 active advisory of type `ground_stop`, `ground_delay_program`, `airport_closure`, `arrival_delay` or `departure_delay`. |
| **Flight category** | AWC METAR `fltCat`: VFR (ceiling > 3000 ft and vis > 5 SM), MVFR (1000–3000 ft or 3–5 SM), IFR (500–<1000 ft or 1–<3 SM), LIFR (< 500 ft or < 1 SM). |
| **Weather risk (observed)** | Derived only from the latest METAR: `low` (VFR, wind < 20 kt), `elevated` (MVFR, or sustained wind/gust ≥ 20 kt), `high` (IFR, or gust ≥ 35 kt, or thunderstorm/freezing precipitation in `wx`), `severe` (LIFR). Observed weather conditions only; not a delay forecast. |

## Airport status colour (map)

Evaluated top-down; first match wins.

1. `ground_stop` active → **critical** (coral)
2. `ground_delay_program` or full `airport_closure` active → **critical** (coral)
3. `arrival_delay`/`departure_delay` active → **warning** (amber)
4. Latest METAR IFR/LIFR → **weather** (amber outline, label "IFR/LIFR conditions")
5. METAR fresh and no advisories → **normal** (mint)
6. No fresh METAR and no advisories → **unknown** (slate)

## Data freshness

Per source, `age = now − last successful ingestion`. Thresholds are multiples of the
expected cadence:

| Source | Expected cadence | Healthy | Delayed | Stale | Unavailable |
|---|---|---|---|---|---|
| FAA NAS Status | 5 min | ≤ 10 min | ≤ 30 min | ≤ 6 h | > 6 h or never |
| AWC METAR | 10 min | ≤ 20 min | ≤ 60 min | ≤ 6 h | > 6 h or never |
| AWC TAF | 30 min | ≤ 60 min | ≤ 3 h | ≤ 12 h | > 12 h or never |
| BTS historical | monthly | ≤ 120 days since data month end | ≤ 180 d | ≤ 365 d | > 365 d or never |

A METAR **observation** is additionally *stale* when `now − observed_at > 2 h`
(routine METARs are hourly), regardless of ingestion health.

**Fresh data** = the source status is `healthy` **and** the record's own observation age
is within its threshold.

## Historical (BTS On-Time Performance)

Denominators exclude nothing unless stated.

| Measure | Definition |
|---|---|
| **Scheduled flights** | Count of BTS rows (each a scheduled flight segment) for the airport as origin (departures) or destination (arrivals). |
| **Operated flights** | Scheduled − cancelled. |
| **Cancellation rate** | Cancelled / scheduled. |
| **Diversion rate** | Diverted / scheduled. |
| **Delayed (arrival)** | Operated, not diverted, `ArrDelay ≥ 15`. |
| **On-time %** (arrival) | Arrivals with `ArrDelay < 15` / operated non-diverted arrivals with a non-null `ArrDelay`. Cancelled and diverted flights are excluded from both numerator and denominator (DOT convention). |
| **Average arrival delay** | Mean `ArrDelay` (early arrivals count as negative) over operated non-diverted arrivals. |
| **Average departure delay** | Mean `DepDelay` over operated departures. |
| **Delay-cause minutes** | Sum of `CarrierDelay`, `WeatherDelay`, `NASDelay`, `SecurityDelay`, `LateAircraftDelay` (reported only for arrivals delayed ≥ 15 min). Shares are of total cause minutes. These are carrier-reported attributions, not proven causes. |
| **MoM / YoY change** | Difference in the measure vs. the same measure for the previous month / the same month one year earlier; blank when the comparison period is outside the loaded data. |

## Risk indicator (Phase 6)

Defined in `docs/dashboards/risk.md` when implemented. A risk score is not a confirmed
delay and is always shown with its model version and timestamp.
