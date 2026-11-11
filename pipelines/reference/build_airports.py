"""Build the AeroPulse airport dimension seed file.

Inputs
------
* OurAirports ``airports.csv`` (public domain) — authoritative coordinates,
  names, ICAO/IATA codes. Download: https://davidmegginson.github.io/ourairports-data/airports.csv
* The curated list of monitored airports + IANA time zones below.

Output
------
``services/api/app/data/airports.csv`` — committed seed consumed by the API
migration/seed step. Re-run this script whenever the monitored set changes:

    python pipelines/reference/build_airports.py /path/to/airports.csv

The script fails loudly if any monitored airport is missing, has a mismatched
ICAO/IATA pair, or is not a large/medium U.S. airport — this is the code-mapping
validation required between FAA (IATA/FAA LID), AWC (ICAO) and BTS (IATA).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

# 50 major U.S. commercial airports (FAA CY passenger enplanement leaders),
# with IANA time zones. Order is not significant.
# PBI is intentionally excluded: OurAirports/FAA now list it as DJT/KDJT (2026
# renaming) while BTS history uses PBI, so the cross-dataset mapping is ambiguous.
MONITORED: dict[str, str] = {
    "ATL": "America/New_York",
    "DFW": "America/Chicago",
    "DEN": "America/Denver",
    "ORD": "America/Chicago",
    "LAX": "America/Los_Angeles",
    "JFK": "America/New_York",
    "LAS": "America/Los_Angeles",
    "MCO": "America/New_York",
    "MIA": "America/New_York",
    "CLT": "America/New_York",
    "SEA": "America/Los_Angeles",
    "PHX": "America/Phoenix",
    "EWR": "America/New_York",
    "SFO": "America/Los_Angeles",
    "IAH": "America/Chicago",
    "BOS": "America/New_York",
    "FLL": "America/New_York",
    "MSP": "America/Chicago",
    "LGA": "America/New_York",
    "DTW": "America/Detroit",
    "PHL": "America/New_York",
    "SLC": "America/Denver",
    "BWI": "America/New_York",
    "DCA": "America/New_York",
    "SAN": "America/Los_Angeles",
    "IAD": "America/New_York",
    "TPA": "America/New_York",
    "BNA": "America/Chicago",
    "AUS": "America/Chicago",
    "MDW": "America/Chicago",
    "HNL": "Pacific/Honolulu",
    "DAL": "America/Chicago",
    "PDX": "America/Los_Angeles",
    "STL": "America/Chicago",
    "RDU": "America/New_York",
    "HOU": "America/Chicago",
    "SMF": "America/Los_Angeles",
    "MSY": "America/Chicago",
    "SJC": "America/Los_Angeles",
    "SNA": "America/Los_Angeles",
    "MCI": "America/Chicago",
    "OAK": "America/Los_Angeles",
    "SAT": "America/Chicago",
    "RSW": "America/New_York",
    "CLE": "America/New_York",
    "IND": "America/Indiana/Indianapolis",
    "PIT": "America/New_York",
    "CVG": "America/New_York",
    "CMH": "America/New_York",
    "JAX": "America/New_York",
}

FIELDS = [
    "iata_code",
    "icao_code",
    "name",
    "city",
    "state",
    "latitude",
    "longitude",
    "elevation_ft",
    "timezone",
    "airport_type",
    "ourairports_id",
]


def build(source: Path, dest: Path) -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with source.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            iata = rec.get("iata_code", "").strip()
            if iata in MONITORED and rec["iso_country"] == "US":
                rows[iata] = rec

    missing = sorted(set(MONITORED) - set(rows))
    if missing:
        raise SystemExit(f"Monitored airports missing from source: {missing}")

    out: list[dict[str, str]] = []
    for iata in sorted(MONITORED):
        rec = rows[iata]
        icao = (rec.get("icao_code") or rec["ident"]).strip()
        # Continental U.S. ICAO = 'K' + IATA; Hawaii uses 'PH' prefix.
        expected_prefix = "PH" if rec["iso_region"] == "US-HI" else "K"
        if not icao.startswith(expected_prefix) or not icao.endswith(iata[-2:]):
            raise SystemExit(f"Suspicious ICAO/IATA mapping {icao}/{iata}")
        if rec["type"] not in {"large_airport", "medium_airport"}:
            raise SystemExit(f"{iata} is not a large/medium airport: {rec['type']}")
        ZoneInfo(MONITORED[iata])  # raises if invalid
        out.append(
            {
                "iata_code": iata,
                "icao_code": icao,
                "name": rec["name"],
                "city": rec["municipality"],
                "state": rec["iso_region"].removeprefix("US-"),
                "latitude": f"{float(rec['latitude_deg']):.6f}",
                "longitude": f"{float(rec['longitude_deg']):.6f}",
                "elevation_ft": rec["elevation_ft"],
                "timezone": MONITORED[iata],
                "airport_type": rec["type"],
                "ourairports_id": rec["id"],
            }
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_airports.py <ourairports airports.csv>")
    repo = Path(__file__).resolve().parents[2]
    result = build(Path(sys.argv[1]), repo / "services/api/app/data/airports.csv")
    print(f"wrote {len(result)} airports")
