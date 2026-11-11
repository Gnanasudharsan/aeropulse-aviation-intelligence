"""BTS Reporting Carrier On-Time Performance -> AeroPulse historical facts.

Streaming, disk-conscious pipeline (one month at a time):

  download zip (if missing) -> sha256 -> extract CSV to a temp dir -> DuckDB aggregate to
  airport x day x direction, airport x month x hour x direction and airport x month x
  carrier x direction -> data-quality checks -> idempotent load into PostgreSQL (delete the
  month, insert) -> lineage row in historical_loads -> remove the CSV (and the zip with
  --delete-raw).

Then (--export DIR) the Power BI star schema is exported as Parquet.

Usage (from the repo root):

  uv run --project services/api --group pipeline python pipelines/historical/bts_pipeline.py \
      --start 2024-09 --end 2026-08 --raw-dir data/raw/bts --delete-raw \
      --export analytics/powerbi/data

Source: https://www.transtats.bts.gov/ (U.S. DOT, public domain). Definitions follow DOT:
a flight is "on time" if it arrives (departs) less than 15 minutes after schedule;
cancelled and diverted flights are excluded from on-time denominators.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import psycopg

REPO = Path(__file__).resolve().parents[2]
AIRPORTS_CSV = REPO / "services/api/app/data/airports.csv"
URL = "https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip"
UA = "AeroPulse/1.0 (+https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence)"

# Reporting carriers (BTS Reporting_Airline codes). Unknown codes fall back to the code itself.
CARRIERS = {
    "AA": "American Airlines",
    "AS": "Alaska Airlines",
    "B6": "JetBlue Airways",
    "DL": "Delta Air Lines",
    "F9": "Frontier Airlines",
    "G4": "Allegiant Air",
    "HA": "Hawaiian Airlines",
    "MQ": "Envoy Air",
    "NK": "Spirit Airlines",
    "OH": "PSA Airlines",
    "OO": "SkyWest Airlines",
    "UA": "United Airlines",
    "WN": "Southwest Airlines",
    "YX": "Republic Airways",
    "9E": "Endeavor Air",
    "QX": "Horizon Air",
    "ZW": "Air Wisconsin",
    "G7": "GoJet Airlines",
    "C5": "CommuteAir",
    "YV": "Mesa Airlines",
    "PT": "Piedmont Airlines",
}

MEASURES = """
    count(*)                                                        AS flights,
    sum(cancelled)                                                  AS cancelled,
    sum(diverted)                                                   AS diverted,
    sum(den)                                                        AS ontime_den,
    sum(CASE WHEN den = 1 AND delay < 15 THEN 1 ELSE 0 END)         AS ontime_num,
    sum(CASE WHEN den = 1 AND delay >= 15 THEN 1 ELSE 0 END)        AS delayed_15,
    sum(CASE WHEN cancel_code = 'A' THEN 1 ELSE 0 END)              AS cancel_carrier,
    sum(CASE WHEN cancel_code = 'B' THEN 1 ELSE 0 END)              AS cancel_weather,
    sum(CASE WHEN cancel_code = 'C' THEN 1 ELSE 0 END)              AS cancel_nas,
    sum(CASE WHEN cancel_code = 'D' THEN 1 ELSE 0 END)              AS cancel_security,
    sum(CASE WHEN den = 1 AND delay < 0 THEN 1 ELSE 0 END)          AS bucket_early,
    sum(CASE WHEN den = 1 AND delay BETWEEN 0 AND 14 THEN 1 ELSE 0 END)   AS bucket_0_14,
    sum(CASE WHEN den = 1 AND delay BETWEEN 15 AND 29 THEN 1 ELSE 0 END)  AS bucket_15_29,
    sum(CASE WHEN den = 1 AND delay BETWEEN 30 AND 59 THEN 1 ELSE 0 END)  AS bucket_30_59,
    sum(CASE WHEN den = 1 AND delay BETWEEN 60 AND 119 THEN 1 ELSE 0 END) AS bucket_60_119,
    sum(CASE WHEN den = 1 AND delay >= 120 THEN 1 ELSE 0 END)       AS bucket_120_plus,
    coalesce(sum(CASE WHEN den = 1 THEN delay END), 0)::BIGINT      AS delay_sum_min,
    coalesce(sum(carrier_delay), 0)::BIGINT                         AS carrier_delay_min,
    coalesce(sum(weather_delay), 0)::BIGINT                         AS weather_delay_min,
    coalesce(sum(nas_delay), 0)::BIGINT                             AS nas_delay_min,
    coalesce(sum(security_delay), 0)::BIGINT                        AS security_delay_min,
    coalesce(sum(late_aircraft_delay), 0)::BIGINT                   AS late_aircraft_delay_min
"""
MEASURE_COLS = [
    "flights",
    "cancelled",
    "diverted",
    "ontime_den",
    "ontime_num",
    "delayed_15",
    "cancel_carrier",
    "cancel_weather",
    "cancel_nas",
    "cancel_security",
    "bucket_early",
    "bucket_0_14",
    "bucket_15_29",
    "bucket_30_59",
    "bucket_60_119",
    "bucket_120_plus",
    "delay_sum_min",
    "carrier_delay_min",
    "weather_delay_min",
    "nas_delay_min",
    "security_delay_min",
    "late_aircraft_delay_min",
]


def log(msg: str, **kv: object) -> None:
    print(json.dumps({"ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "msg": msg, **kv}), flush=True)


def months(start: str, end: str) -> list[tuple[int, int]]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def monitored() -> list[str]:
    with AIRPORTS_CSV.open() as fh:
        return [r["iata_code"] for r in csv.DictReader(fh)]


def download(y: int, m: int, raw_dir: Path) -> Path:
    path = raw_dir / f"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip"
    if path.exists() and path.stat().st_size > 0:
        return path
    raw_dir.mkdir(parents=True, exist_ok=True)
    url = URL.format(y=y, m=m)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as resp, open(f"{path}.part", "wb") as out:
                while chunk := resp.read(1 << 20):
                    out.write(chunk)
            os.replace(f"{path}.part", path)
            return path
        except Exception as exc:
            log("download_retry", month=f"{y}-{m:02d}", attempt=attempt, error=str(exc))
            time.sleep(5 * 2**attempt)
    raise SystemExit(f"could not download {url}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def aggregate(csv_path: Path, codes: list[str], training_file: Path | None = None) -> dict[str, list[tuple]]:
    con = duckdb.connect()
    con.execute(
        "CREATE TEMP TABLE f AS SELECT * FROM read_csv(?, header=true, all_varchar=true, ignore_errors=false)",
        [str(csv_path)],
    )
    con.execute("CREATE TEMP TABLE mon(code VARCHAR)")
    con.executemany("INSERT INTO mon VALUES (?)", [(c,) for c in codes])
    legs_common = """
        CAST(FlightDate AS DATE) AS flight_date,
        Reporting_Airline AS carrier,
        CAST(CAST(Cancelled AS DOUBLE) AS INTEGER) AS cancelled,
        CAST(CAST(Diverted AS DOUBLE) AS INTEGER) AS diverted,
        NULLIF(CancellationCode, '') AS cancel_code,
        TRY_CAST(CarrierDelay AS DOUBLE) AS carrier_delay,
        TRY_CAST(WeatherDelay AS DOUBLE) AS weather_delay,
        TRY_CAST(NASDelay AS DOUBLE) AS nas_delay,
        TRY_CAST(SecurityDelay AS DOUBLE) AS security_delay,
        TRY_CAST(LateAircraftDelay AS DOUBLE) AS late_aircraft_delay
    """
    con.execute(
        f"""
        CREATE TEMP TABLE legs AS
        SELECT Origin AS airport, 'departure' AS direction, {legs_common},
               (TRY_CAST(CRSDepTime AS INTEGER) // 100) % 24 AS hour_local,
               TRY_CAST(DepDelay AS DOUBLE) AS delay,
               CASE WHEN CAST(CAST(Cancelled AS DOUBLE) AS INTEGER) = 0
                         AND TRY_CAST(DepDelay AS DOUBLE) IS NOT NULL THEN 1 ELSE 0 END AS den
        FROM f WHERE Origin IN (SELECT code FROM mon)
        UNION ALL
        SELECT Dest, 'arrival', {legs_common},
               (TRY_CAST(CRSArrTime AS INTEGER) // 100) % 24,
               TRY_CAST(ArrDelay AS DOUBLE),
               CASE WHEN CAST(CAST(Cancelled AS DOUBLE) AS INTEGER) = 0
                         AND CAST(CAST(Diverted AS DOUBLE) AS INTEGER) = 0
                         AND TRY_CAST(ArrDelay AS DOUBLE) IS NOT NULL THEN 1 ELSE 0 END
        FROM f WHERE Dest IN (SELECT code FROM mon)
        """
    )
    q = {
        "daily": f"SELECT airport, flight_date, direction, {MEASURES} FROM legs GROUP BY ALL ORDER BY ALL",
        "hourly": f"""SELECT airport, date_trunc('month', flight_date)::DATE, direction, hour_local, {MEASURES}
                      FROM legs WHERE hour_local IS NOT NULL GROUP BY ALL ORDER BY ALL""",
        "carrier": f"""SELECT airport, date_trunc('month', flight_date)::DATE, direction, carrier, {MEASURES}
                       FROM legs GROUP BY ALL ORDER BY ALL""",
    }
    out = {k: con.execute(v).fetchall() for k, v in q.items()}
    if training_file is not None:
        # Model-training extract (Phase 6): departures by airport x date x scheduled local hour.
        training_file.parent.mkdir(parents=True, exist_ok=True)
        con.execute(
            f"""COPY (
                SELECT airport, flight_date, hour_local, count(*) AS flights, sum(cancelled) AS cancelled,
                       sum(den) AS ontime_den,
                       sum(CASE WHEN den = 1 AND delay >= 15 THEN 1 ELSE 0 END) AS delayed_15,
                       sum(CASE WHEN den = 1 AND delay >= 60 THEN 1 ELSE 0 END) AS delayed_60
                FROM legs WHERE direction = 'departure' AND hour_local IS NOT NULL
                GROUP BY ALL ORDER BY ALL
            ) TO '{training_file}' (FORMAT parquet)"""
        )
    stats = con.execute(
        """SELECT (SELECT count(*) FROM f),
                  (SELECT count(*) FROM legs),
                  (SELECT count(DISTINCT airport) FROM legs),
                  (SELECT count(*) FROM f WHERE FlightDate IS NULL OR FlightDate = ''),
                  (SELECT count(*) FROM f WHERE Flights IS NOT NULL AND CAST(Flights AS DOUBLE) <> 1),
                  (SELECT min(CAST(FlightDate AS DATE)) FROM f),
                  (SELECT max(CAST(FlightDate AS DATE)) FROM f),
                  (SELECT count(*) FROM legs WHERE hour_local IS NULL),
                  (SELECT count(DISTINCT carrier) FROM legs)"""
    ).fetchone()
    out["_stats"] = [stats]
    con.close()
    return out


def quality(y: int, m: int, agg: dict[str, list[tuple]], codes: list[str]) -> dict[str, object]:
    rows_read, legs, airports_seen, null_dates, bad_flights, dmin, dmax, null_hours, carriers = agg["_stats"][0]
    daily_flights = sum(r[3] for r in agg["daily"])
    hourly_flights = sum(r[4] for r in agg["hourly"])
    checks = {
        "rows_read": rows_read,
        "monitored_legs": legs,
        "airports_seen": airports_seen,
        "missing_flight_date": null_dates,
        "flights_not_one": bad_flights,
        "date_range": [str(dmin), str(dmax)],
        "legs_missing_scheduled_hour": null_hours,
        "carriers": carriers,
        "daily_equals_legs": daily_flights == legs,
        "hourly_plus_missing_equals_legs": hourly_flights + null_hours == legs,
    }
    errors = []
    if rows_read == 0:
        errors.append("empty file")
    if airports_seen != len(codes):
        errors.append(f"only {airports_seen}/{len(codes)} monitored airports present")
    if null_dates:
        errors.append(f"{null_dates} rows without FlightDate")
    if dmin is None or (dmin.year, dmin.month) != (y, m) or (dmax.year, dmax.month) != (y, m):
        errors.append(f"dates {dmin}..{dmax} outside {y}-{m:02d}")
    if not checks["daily_equals_legs"] or not checks["hourly_plus_missing_equals_legs"]:
        errors.append("aggregate reconciliation failed")
    checks["errors"] = errors
    return checks


def load(conn: psycopg.Connection, y: int, m: int, agg: dict[str, list[tuple]], meta: dict[str, object]) -> None:
    month = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    cols = ", ".join(MEASURE_COLS)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM airport_performance_daily WHERE flight_date >= %s AND flight_date < %s", (month, nxt))
        cur.execute("DELETE FROM airport_performance_hourly WHERE year_month = %s", (month,))
        cur.execute("DELETE FROM carrier_performance_monthly WHERE year_month = %s", (month,))
        for table, keys, rows in (
            ("airport_performance_daily", "airport_iata, flight_date, direction", agg["daily"]),
            ("airport_performance_hourly", "airport_iata, year_month, direction, hour_local", agg["hourly"]),
            ("carrier_performance_monthly", "airport_iata, year_month, direction, carrier_code", agg["carrier"]),
        ):
            with cur.copy(f"COPY {table} ({keys}, {cols}) FROM STDIN") as cp:
                for r in rows:
                    cp.write_row(r)
        codes = sorted({r[3] for r in agg["carrier"]})
        cur.executemany(
            "INSERT INTO carriers (carrier_code, carrier_name) VALUES (%s, %s) "
            "ON CONFLICT (carrier_code) DO UPDATE SET carrier_name = EXCLUDED.carrier_name",
            [(c, CARRIERS.get(c, c)) for c in codes],
        )
        cur.execute(
            """INSERT INTO historical_loads (year_month, source_file, source_sha256, rows_read, rows_monitored, quality)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (year_month) DO UPDATE SET source_file = EXCLUDED.source_file,
                 source_sha256 = EXCLUDED.source_sha256, rows_read = EXCLUDED.rows_read,
                 rows_monitored = EXCLUDED.rows_monitored, quality = EXCLUDED.quality, loaded_at = now()""",
            (month, meta["file"], meta["sha256"], meta["rows_read"], meta["legs"], json.dumps(meta["quality"])),
        )


def mark_source(conn: psycopg.Connection) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT max(year_month), sum(rows_monitored) FROM historical_loads")
        latest, total = cur.fetchone()
        if latest is None:
            return
        month_end = dt.date(latest.year + (latest.month == 12), latest.month % 12 + 1, 1)
        cur.execute(
            """INSERT INTO source_status (source, display_name, source_url, expected_interval_seconds,
                     last_attempt_at, last_success_at, consecutive_failures, last_observation_at,
                     last_source_published_at, last_record_count)
               VALUES ('bts_ontime', 'BTS — Reporting Carrier On-Time Performance',
                       'https://www.transtats.bts.gov/', 2592000, now(), now(), 0, %s, NULL, %s)
               ON CONFLICT (source) DO UPDATE SET last_attempt_at = now(), last_success_at = now(),
                     consecutive_failures = 0, last_error = NULL,
                     last_observation_at = EXCLUDED.last_observation_at,
                     last_record_count = EXCLUDED.last_record_count""",
            (dt.datetime.combine(month_end, dt.time(), tzinfo=dt.UTC), total),
        )


EXPORTS = {
    "dim_airport": "SELECT iata_code, icao_code, name, city, state, latitude, longitude, timezone FROM airports WHERE is_monitored",
    "dim_carrier": "SELECT carrier_code, carrier_name FROM carriers",
    "fact_airport_daily": "SELECT * FROM airport_performance_daily ORDER BY flight_date, airport_iata, direction",
    "fact_airport_hourly": "SELECT * FROM airport_performance_hourly ORDER BY year_month, airport_iata, direction, hour_local",
    "fact_carrier_monthly": "SELECT * FROM carrier_performance_monthly ORDER BY year_month, airport_iata, direction, carrier_code",
    "data_lineage": "SELECT year_month, source_file, source_sha256, rows_read, rows_monitored, loaded_at FROM historical_loads ORDER BY year_month",
}


def export(conn: psycopg.Connection, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    with tempfile.TemporaryDirectory() as tmp:
        for name, sql in EXPORTS.items():
            csv_path = Path(tmp) / f"{name}.csv"
            with (
                conn.cursor() as cur,
                csv_path.open("wb") as fh,
                cur.copy(f"COPY ({sql}) TO STDOUT WITH CSV HEADER") as cp,
            ):
                for chunk in cp:
                    fh.write(chunk)
            target = out_dir / f"{name}.parquet"
            con.execute(
                f"COPY (SELECT * FROM read_csv('{csv_path}', header=true)) TO '{target}' (FORMAT parquet, COMPRESSION zstd)"
            )
            log("exported", table=name, bytes=target.stat().st_size)
        # Date dimension spanning the loaded facts (Power BI can also mark it as a date table).
        with conn.cursor() as cur:
            cur.execute("SELECT min(flight_date), max(flight_date) FROM airport_performance_daily")
            lo, hi = cur.fetchone()
        if lo:
            con.execute(
                f"""COPY (
                    SELECT d::DATE AS date, year(d) AS year, quarter(d) AS quarter, month(d) AS month,
                           strftime(d, '%b') AS month_short, strftime(d, '%Y-%m') AS year_month,
                           date_trunc('month', d)::DATE AS month_start, isodow(d) AS iso_day_of_week,
                           strftime(d, '%a') AS day_short, isodow(d) >= 6 AS is_weekend,
                           CASE WHEN month(d) IN (12,1,2) THEN 'Winter' WHEN month(d) IN (3,4,5) THEN 'Spring'
                                WHEN month(d) IN (6,7,8) THEN 'Summer' ELSE 'Autumn' END AS season
                    FROM range(DATE '{lo}', DATE '{hi}' + 1, INTERVAL 1 DAY) t(d)
                ) TO '{out_dir / "dim_date.parquet"}' (FORMAT parquet)"""
            )
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM")
    ap.add_argument("--end", required=True, help="YYYY-MM")
    ap.add_argument("--raw-dir", type=Path, default=REPO / "data/raw/bts")
    ap.add_argument("--delete-raw", action="store_true", help="delete each zip after a successful load")
    ap.add_argument("--export", type=Path, help="write the Power BI star schema as Parquet here")
    ap.add_argument("--skip-loaded", action="store_true", help="skip DB load for months already in historical_loads")
    ap.add_argument("--training-dir", type=Path, help="also write per-date-hour departure extracts (model training)")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL", "postgresql://aeropulse:change-me-locally@localhost:5442/aeropulse")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    codes = monitored()
    failed = []
    with psycopg.connect(url) as conn:
        loaded = set()
        if args.skip_loaded:
            with conn.cursor() as cur:
                cur.execute("SELECT year_month FROM historical_loads")
                loaded = {(r[0].year, r[0].month) for r in cur.fetchall()}
        for y, m in months(args.start, args.end):
            need_load = (y, m) not in loaded
            train_file = args.training_dir / f"departures_{y}_{m:02d}.parquet" if args.training_dir else None
            need_train = train_file is not None and not train_file.exists()
            if not need_load and not need_train:
                log("skip", month=f"{y}-{m:02d}")
                continue
            started = time.monotonic()
            zpath = download(y, m, args.raw_dir)
            digest = sha256(zpath)
            with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(zpath) as zf:
                name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
                csv_path = Path(zf.extract(name, tmp))
                agg = aggregate(csv_path, codes, train_file if need_train else None)
            q = quality(y, m, agg, codes)
            if q["errors"]:
                log("quality_failed", month=f"{y}-{m:02d}", **q)
                failed.append(f"{y}-{m:02d}")
                if train_file is not None and train_file.exists():
                    train_file.unlink()
                continue
            if need_load:
                meta = {
                    "file": zpath.name,
                    "sha256": digest,
                    "rows_read": q["rows_read"],
                    "legs": q["monitored_legs"],
                    "quality": q,
                }
                load(conn, y, m, agg, meta)
            if args.delete_raw:
                zpath.unlink()
            log(
                "month_done",
                month=f"{y}-{m:02d}",
                loaded=need_load,
                training=need_train,
                rows_read=q["rows_read"],
                legs=q["monitored_legs"],
                seconds=round(time.monotonic() - started, 1),
            )
        mark_source(conn)
        if args.export:
            export(conn, args.export)
    if failed:
        log("months_failed_quality", months=failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
