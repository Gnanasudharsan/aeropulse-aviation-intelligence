# Data sources — verification log

All sources below were probed from the development machine on **2026-11-11 (UTC)**
before any ingestion code was written. Findings drive the parsers, the polling
cadence and the freshness thresholds.

| Source | Endpoint used | Format | Auth | Our cadence | Upstream cadence |
|---|---|---|---|---|---|
| FAA NAS Status — airport events | `https://nasstatus.faa.gov/api/airport-events` | JSON | none | 5 min | event driven (minutes) |
| FAA NAS Status — airport status (legacy) | `https://nasstatus.faa.gov/api/airport-status-information` | XML | none | 5 min (bronze + fallback) | event driven; `Update_Time` header |
| NOAA AWC — METAR | `https://aviationweather.gov/api/data/metar?format=json` | JSON | none | 10 min | hourly routine + SPECI |
| NOAA AWC — TAF | `https://aviationweather.gov/api/data/taf?format=json` | JSON | none | 30 min | ~6 h issuance + amendments |
| BTS — Reporting Carrier On-Time Performance | `https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{YYYY}_{M}.zip` | zipped CSV | none | monthly | monthly, ~2–3 month lag |
| OurAirports — reference | `https://davidmegginson.github.io/ourairports-data/airports.csv` | CSV | none | on change | nightly |

## FAA NAS Status

The FAA's public NAS Status site (`nasstatus.faa.gov`) is a single-page app backed
by JSON endpoints under `/api/`. The site **does not publish a formal API contract**
for these endpoints. We therefore treat them conservatively:

* `airport-events` (JSON) is the **primary** event source because each event carries
  a stable UUID (`id`), ISO-8601 UTC `startTime`/`endTime`/`updatedAt`, and typed
  sub-objects: `groundStop`, `groundDelay`, `airportClosure`, `freeForm` (NOTAM-style
  closures), `arrivalDelay`, `departureDelay`, `deicing`, `airportConfig`.
  Field names were confirmed from the live payload and the site's own JS bundle
  (e.g. `groundDelay.avgDelay`, `groundStop.probabilityOfExtension`,
  `arrivalDelay.averageDelay`, `arrivalDelay.trend`).
* `airport-status-information` (XML) is the long-standing FAA "Airport Status"
  feed. It provides a feed-level `Update_Time` (our **source publication time**)
  and is used as a **fallback parser** when the JSON endpoint fails or changes shape.
* `robots.txt` on `nasstatus.faa.gov` has no disallow rules. We poll at most once
  every 5 minutes per endpoint with a descriptive `User-Agent`, honour HTTP errors
  with exponential backoff, and never scrape HTML.
* **Scope caveat:** NAS Status lists only airports with *active* events. An airport
  absent from the feed means "no event reported", not "verified normal".
* `airportConfig` (runway configuration / arrival rate) is informational, not a
  disruption, and is stored separately from advisories.
* `freeForm` items are frequently long-running NOTAM closures that apply only to a
  subset of operations (e.g. *"CLSD TO NON SKED TRANSIENT GA ACFT"*). They are
  classified as `closure_notam` with `scope = partial` and never counted as a
  full airport closure.

## NOAA Aviation Weather Center (AWC) Data API

Documented at <https://aviationweather.gov/data/api/>. Usage notes we follow:

* Batch station ids in a single request (`ids=KATL,KBOS,…`) — 50 stations per call.
* Descriptive `User-Agent`; ≤ 1 request / minute per product in practice
  (AWC's documented limit is 100 req/min; we use < 1 % of it).
* METAR `obsTime` (epoch seconds) is the **observation time**; `receiptTime` is when
  AWC received it; `reportTime` is the nominal report hour. A re-fetch of an unchanged
  METAR is deduplicated on `(station, obs_time, raw_text hash)` and is **not** a new
  observation.
* `visib` is a string (`"10+"`, `"1/2"`, `"6+"`); we parse it into statute miles and keep
  the original text plus a `visibility_is_lower_bound` flag.
* `fltCat` (VFR/MVFR/IFR/LIFR) is supplied by AWC; we store it as delivered and
  only compute it ourselves (from ceiling/visibility) when absent, flagging
  `flight_category_source = 'derived'`.
* TAF `fcsts[]` periods carry `timeFrom`/`timeTo`, change indicators (`FM`, `TEMPO`,
  `BECMG`, `PROB`) and per-period wind/visibility/cloud groups. We store one row per
  TAF issuance plus one row per forecast period.

## BTS Reporting Carrier On-Time Performance

* Latest available month at verification time: **August 2026** (`2026_8`, 32 MB zipped);
  September/October 2026 return 404 (normal 2–3 month publishing lag).
* One row per scheduled domestic flight by reporting carriers, with `ArrDelay`,
  `DepDelay`, `Cancelled`, `Diverted`, and delay-cause minutes (`CarrierDelay`,
  `WeatherDelay`, `NASDelay`, `SecurityDelay`, `LateAircraftDelay`).
* Raw zips are downloaded to `data/raw/` (git-ignored) and aggregated to airport ×
  local-date × local-hour facts for the 50 monitored airports. Only the aggregates
  enter PostgreSQL / Power BI. See `pipelines/historical/README.md`.
* BTS "on time" = arrived < 15 minutes after schedule (DOT definition); delay-cause
  minutes are only reported for flights with ≥ 15 minutes arrival delay.

## OurAirports

Public-domain airport reference used for coordinates/names/ICAO↔IATA validation.
`pipelines/reference/build_airports.py` fails the build on any missing airport,
suspicious ICAO/IATA pair, or invalid IANA time zone.

**Known identifier issue:** Palm Beach International now appears as `DJT`/`KDJT`
in reference data while BTS history uses `PBI`. Because the mapping is ambiguous
across sources, PBI is excluded from the monitored set and JAX is used instead.
