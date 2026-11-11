"""Historical METARs for model training, from the Iowa Environmental Mesonet ASOS archive.

AWC's live API only serves recent observations, so training features come from IEM
(https://mesonet.agron.iastate.edu/request/download.phtml), which redistributes the same
NWS/FAA METARs. Requests are sequential, one station at a time, with a descriptive UA.

    uv run --project services/api --group pipeline python pipelines/historical/iem_metar_history.py \
        --start 2024-09-01 --end 2026-09-01 --out data/derived/metar_history

Output: one Parquet file per station with UTC observation time, temperature, wind, gust,
visibility, cloud layers (ceiling derived), present-weather codes and flight category.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
UA = "AeroPulse/1.0 (+https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence)"
BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
FIELDS = [
    "tmpf",
    "sknt",
    "gust",
    "vsby",
    "skyc1",
    "skyl1",
    "skyc2",
    "skyl2",
    "skyc3",
    "skyl3",
    "skyc4",
    "skyl4",
    "wxcodes",
]


def stations() -> list[tuple[str, str]]:
    with (REPO / "services/api/app/data/airports.csv").open() as fh:
        # IEM uses the FAA identifier for U.S. stations (JFK, HNL).
        return [(r["iata_code"], r["icao_code"]) for r in csv.DictReader(fh)]


def fetch(station: str, start: str, end: str) -> str:
    y1, m1, d1 = start.split("-")
    y2, m2, d2 = end.split("-")
    params = [
        ("station", station),
        *[("data", f) for f in FIELDS],
        ("year1", y1),
        ("month1", m1),
        ("day1", d1),
        ("year2", y2),
        ("month2", m2),
        ("day2", d2),
        ("tz", "Etc/UTC"),
        ("format", "onlycomma"),
        ("latlon", "no"),
        ("missing", "null"),
        ("trace", "null"),
        ("direct", "no"),
        ("report_type", "3"),
        ("report_type", "4"),
    ]
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read().decode()
        except Exception as exc:
            print(json.dumps({"msg": "retry", "station": station, "attempt": attempt, "error": str(exc)}), flush=True)
            time.sleep(10 * 2**attempt)
    raise SystemExit(f"IEM download failed for {station}")


SQL = """
COPY (
  SELECT ? AS airport, ? AS station_icao,
         strptime(valid, '%Y-%m-%d %H:%M')::TIMESTAMP AS observed_utc,
         TRY_CAST(tmpf AS DOUBLE) AS temp_f,
         TRY_CAST(sknt AS DOUBLE) AS wind_kt,
         TRY_CAST(gust AS DOUBLE) AS gust_kt,
         TRY_CAST(vsby AS DOUBLE) AS visibility_sm,
         least(
           CASE WHEN skyc1 IN ('BKN','OVC','VV') THEN TRY_CAST(skyl1 AS DOUBLE) END,
           CASE WHEN skyc2 IN ('BKN','OVC','VV') THEN TRY_CAST(skyl2 AS DOUBLE) END,
           CASE WHEN skyc3 IN ('BKN','OVC','VV') THEN TRY_CAST(skyl3 AS DOUBLE) END,
           CASE WHEN skyc4 IN ('BKN','OVC','VV') THEN TRY_CAST(skyl4 AS DOUBLE) END
         ) AS ceiling_ft,
         NULLIF(wxcodes, 'null') AS wxcodes
  FROM read_csv(?, header=true, all_varchar=true, nullstr='null')
  WHERE valid IS NOT NULL
) TO ? (FORMAT parquet)
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", type=Path, default=REPO / "data/derived/metar_history")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for iata, icao in stations():
        target = args.out / f"{iata}.parquet"
        if target.exists():
            continue
        text = fetch(iata, args.start, args.end)
        tmp = args.out / f"{iata}.csv"
        tmp.write_text(text)
        con.execute(SQL, [iata, icao, str(tmp), str(target)])
        rows = con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0]
        tmp.unlink()
        print(json.dumps({"msg": "station_done", "station": iata, "rows": rows}), flush=True)
        time.sleep(2)  # be polite to IEM


if __name__ == "__main__":
    main()
