from __future__ import annotations

import csv
import datetime as dt
import io
from collections import Counter
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app import repositories as repo
from app.api.deps import DbSession, meta, now_utc, page_meta
from app.ingestion.faa import ADVISORY_TYPES
from app.models import FaaAdvisory, OperationalEvent
from app.schemas import (
    AdvisoryDetailOut,
    AdvisoryOut,
    CategoryCount,
    Envelope,
    OperationalEventOut,
    OperationsSummaryOut,
)
from app.services import assemblers as asm

router = APIRouter(prefix="/operations", tags=["operations"])

AdvisoryType = Literal[
    "ground_stop",
    "ground_delay_program",
    "airport_closure",
    "closure_notam",
    "arrival_delay",
    "departure_delay",
    "deicing",
]
assert set(AdvisoryType.__args__) == set(ADVISORY_TYPES)  # type: ignore[attr-defined]
EventType = Literal["created", "updated", "cleared", "reopened"]
CATEGORIES = ("VFR", "MVFR", "IFR", "LIFR")


@router.get(
    "/summary",
    response_model=Envelope[OperationsSummaryOut],
    summary="National command-center summary",
)
def summary(db: DbSession, response: Response) -> Envelope[OperationsSummaryOut]:
    response.headers["Cache-Control"] = "public, max-age=15"
    now = now_utc()
    fresh = asm.all_freshness(db, now)
    airports = asm.airport_summaries(db, now)
    cats = Counter(
        a.flight_category for a in airports if a.flight_category and not a.weather_is_stale
    )
    status_counts = Counter(a.status for a in airports)
    latest_obs = max(
        (a.weather_observed_at for a in airports if a.weather_observed_at), default=None
    )
    data = OperationsSummaryOut(
        monitored_airports=len(airports),
        airports_with_active_advisories=sum(1 for a in airports if a.active_advisories > 0),
        airports_with_disruptions=sum(
            1
            for a in airports
            if a.has_ground_stop
            or a.has_ground_delay_program
            or a.has_full_closure
            or a.has_reported_delay
        ),
        active_ground_stops=sum(a.has_ground_stop for a in airports),
        active_ground_delay_programs=sum(a.has_ground_delay_program for a in airports),
        active_full_closures=sum(a.has_full_closure for a in airports),
        active_reported_delays=sum(a.has_reported_delay for a in airports),
        active_partial_closures=sum(a.has_partial_closure for a in airports),
        status_counts={
            s: status_counts.get(s, 0)
            for s in ("critical", "warning", "weather", "normal", "unknown")
        },
        flight_categories=[CategoryCount(category=c, airports=cats.get(c, 0)) for c in CATEGORIES],
        changes_last_hour=repo.count_events_since(db, now - dt.timedelta(hours=1)),
        recent_changes=[asm.event_out(e) for e in repo.recent_events(db, 12)],
        faa_health=fresh["faa_nas_status"].health,
        weather_health=fresh["awc_metar"].health,
        faa_last_success_at=fresh["faa_nas_status"].last_success_at,
        weather_last_success_at=fresh["awc_metar"].last_success_at,
        latest_observation_at=latest_obs,
    )
    return Envelope(data=data, meta=meta())


_ADV_SORT = {
    "last_seen": FaaAdvisory.last_seen_at.desc(),
    "first_seen": FaaAdvisory.first_seen_at.desc(),
    "starts_at": FaaAdvisory.starts_at.desc().nulls_last(),
    "airport": FaaAdvisory.airport_code.asc(),
}


@router.get(
    "/advisories", response_model=Envelope[list[AdvisoryOut]], summary="Search FAA advisories"
)
def advisories(
    db: DbSession,
    response: Response,
    state: Annotated[Literal["active", "inactive", "all"], Query()] = "active",
    airport: Annotated[str | None, Query(max_length=4)] = None,
    type: Annotated[list[AdvisoryType] | None, Query()] = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
    sort: Literal["last_seen", "first_seen", "starts_at", "airport"] = "last_seen",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> Envelope[list[AdvisoryOut]]:
    response.headers["Cache-Control"] = "public, max-age=15"
    now = now_utc()
    stmt = repo.advisories_query(
        now=now, airport=airport, advisory_types=type, state=state, since=since, until=until, q=q
    )
    rows, total = repo.paginate(db, stmt, [_ADV_SORT[sort], FaaAdvisory.id.desc()], page, page_size)
    return Envelope(
        data=[asm.advisory_out(a, now) for a in rows], meta=page_meta(page, page_size, total)
    )


@router.get("/advisories/{advisory_id}", response_model=Envelope[AdvisoryDetailOut])
def advisory_detail(advisory_id: int, db: DbSession) -> Envelope[AdvisoryDetailOut]:
    adv = db.get(FaaAdvisory, advisory_id)
    if adv is None:
        raise HTTPException(status_code=404, detail=f"Advisory {advisory_id} not found")
    now = now_utc()
    base = asm.advisory_out(adv, now)
    detail = AdvisoryDetailOut(
        **base.model_dump(),
        timeline=[asm.event_out(e) for e in repo.advisory_timeline(db, advisory_id)],
    )
    return Envelope(data=detail, meta=meta())


_CSV_FIELDS = [
    "id",
    "detected_at",
    "event_type",
    "airport_code",
    "advisory_type",
    "advisory_id",
    "source_updated_at",
    "changes",
]


@router.get(
    "/events",
    response_model=Envelope[list[OperationalEventOut]],
    summary="Operational change log (advisory created/updated/cleared)",
    responses={200: {"content": {"text/csv": {}}}},
)
def events(
    db: DbSession,
    response: Response,
    airport: Annotated[str | None, Query(max_length=4)] = None,
    type: Annotated[list[AdvisoryType] | None, Query()] = None,
    event_type: Annotated[list[EventType] | None, Query()] = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    sort: Literal["newest", "oldest"] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    format: Literal["json", "csv"] = "json",
) -> Envelope[list[OperationalEventOut]] | StreamingResponse:
    if since and until and since > until:
        raise HTTPException(status_code=422, detail="'since' must be before 'until'")
    stmt = repo.events_query(
        airport=airport, advisory_types=type, event_types=event_type, since=since, until=until
    )
    order: list[Any] = (
        [OperationalEvent.detected_at.desc(), OperationalEvent.id.desc()]
        if sort == "newest"
        else [OperationalEvent.detected_at.asc(), OperationalEvent.id.asc()]
    )
    if format == "csv":
        rows = db.scalars(stmt.order_by(*order).limit(10_000)).all()
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for e in rows:
            out = asm.event_out(e).model_dump(mode="json")
            out["changes"] = str(out["changes"]) if out["changes"] else ""
            writer.writerow({k: out[k] for k in _CSV_FIELDS})
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="aeropulse-events.csv"'},
        )
    response.headers["Cache-Control"] = "public, max-age=15"
    items, total = repo.paginate(db, stmt, order, page, page_size)
    return Envelope(data=[asm.event_out(e) for e in items], meta=page_meta(page, page_size, total))
