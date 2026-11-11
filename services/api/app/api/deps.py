from __future__ import annotations

import datetime as dt
import re
from typing import Annotated

from fastapi import Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app import repositories as repo
from app.db.session import get_db
from app.models import Airport
from app.schemas import Meta

DbSession = Annotated[Session, Depends(get_db)]

_CODE_RE = re.compile(r"^[A-Za-z0-9]{3,4}$")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def meta(**kwargs: int | None) -> Meta:
    return Meta(generated_at=now_utc(), **kwargs)


def page_meta(page: int, page_size: int, total: int) -> Meta:
    return meta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max((total + page_size - 1) // page_size, 1),
    )


def get_airport(
    db: DbSession,
    code: Annotated[
        str, Path(description="IATA (e.g. JFK) or ICAO (e.g. KJFK) code", max_length=4)
    ],
) -> Airport:
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=422, detail=f"Invalid airport code '{code}'")
    airport = repo.find_airport(db, code)
    if airport is None or not airport.is_monitored:
        raise HTTPException(status_code=404, detail=f"Airport '{code.upper()}' is not monitored")
    return airport


AirportDep = Annotated[Airport, Depends(get_airport)]
