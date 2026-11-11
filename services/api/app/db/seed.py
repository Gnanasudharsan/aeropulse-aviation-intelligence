"""Idempotent reference-data seeding (airport dimension)."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingestion.persistence import ensure_source_rows
from app.models import Airport

AIRPORTS_CSV = Path(__file__).resolve().parents[1] / "data" / "airports.csv"


def load_airport_rows(path: Path = AIRPORTS_CSV) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [
            {
                "iata_code": r["iata_code"],
                "icao_code": r["icao_code"],
                "name": r["name"],
                "city": r["city"],
                "state": r["state"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "elevation_ft": int(r["elevation_ft"]) if r["elevation_ft"] else None,
                "timezone": r["timezone"],
                "airport_type": r["airport_type"],
                "is_monitored": True,
                "reference_source": "ourairports",
                "reference_id": r["ourairports_id"],
            }
            for r in csv.DictReader(fh)
        ]


def seed_airports(session: Session) -> int:
    rows = load_airport_rows()
    stmt = pg_insert(Airport).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Airport.iata_code],
        set_={c: stmt.excluded[c] for c in rows[0] if c != "iata_code"},
    )
    session.execute(stmt)
    ensure_source_rows(session)
    return len(rows)
