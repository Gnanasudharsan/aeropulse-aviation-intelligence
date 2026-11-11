# Historical pipeline — BTS On-Time Performance

`bts_pipeline.py` loads U.S. DOT BTS *Reporting Carrier On-Time Performance* monthly files
into the AeroPulse historical facts and exports the Power BI star schema.

```bash
# from the repository root, with the database running (docker compose up -d db migrate)
uv run --project services/api --group pipeline python pipelines/historical/bts_pipeline.py \
  --start 2024-09 --end 2026-08 --raw-dir data/raw/bts --delete-raw --export analytics/powerbi/data
uv run --project services/api --group pipeline python analytics/powerbi/generate_pbip.py
```

## Steps per month (streaming, ~300 MB peak disk)

1. Download `PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{Y}_{M}.zip`
   (~30 MB) with retries; record its SHA-256.
2. Extract the CSV (~280 MB) to a temporary directory; DuckDB reads it as text and casts
   explicitly.
3. Build *legs*: each flight is counted once at its origin (`departure`) and once at its
   destination (`arrival`), for monitored airports only.
4. Aggregate to three additive facts: airport × day × direction, airport × month × direction ×
   scheduled local hour, airport × month × direction × carrier.
5. Quality gates (a month failing any gate is **not loaded**): non-empty file; all 50
   monitored airports present; no missing `FlightDate`; all dates inside the month;
   aggregate reconciliation (daily totals = legs; hourly + unknown-hour = legs).
6. Idempotent load in one transaction: delete the month, `COPY` the new rows, upsert
   carriers, record lineage (`historical_loads`: file, SHA-256, rows, quality JSON).
7. Delete the CSV (and the zip with `--delete-raw`). Raw files are never committed.

`source_status.bts_ontime.last_observation_at` is set to the end of the latest loaded month,
so freshness is measured from data coverage, not from when the job ran.

## Definitions

* On-time: < 15 minutes late (DOT). Denominator excludes cancelled flights (and diverted
  flights for arrivals) and flights without a reported delay.
* Delay-cause minutes are carrier-reported for arrivals ≥ 15 minutes late; they are also
  attributed to the departure leg at the origin for origin-side analysis.
* Scheduled local hour = `CRSDepTime` / `CRSArrTime` hour (local time at the airport).
