"""Disruption Risk Intelligence endpoints (derived indicators — not reported events)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy import text

from app.api.deps import AirportDep, DbSession, meta, now_utc
from app.schemas import Envelope, Model
from app.services.risk import METHOD_VERSION
from app.services.risk_model import model_card

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskComponent(Model):
    key: str
    label: str
    points: float
    max_points: float
    detail: str
    source: str


class RiskScoreOut(Model):
    airport_iata: str
    name: str | None = None
    computed_at: dt.datetime
    method_version: str
    score: float
    category: str
    components: list[RiskComponent]
    missing_inputs: list[str]
    model_version: str | None
    model_probability: float | None
    model_contributions: list[dict[str, Any]] | None
    inputs_as_of: dict[str, Any]


class RiskOverviewOut(Model):
    method_version: str
    computed_at: dt.datetime | None
    is_stale: bool
    category_counts: dict[str, int]
    airports: list[RiskScoreOut]
    model: dict[str, Any] | None
    disclaimer: str = (
        "A risk score summarises conditions associated with disruption. It is not a confirmed delay and "
        "does not predict the outcome of any specific flight."
    )


class RiskPoint(Model):
    computed_at: dt.datetime
    score: float
    category: str
    model_probability: float | None


class AirportRiskOut(Model):
    latest: RiskScoreOut | None
    history: list[RiskPoint]


@router.get(
    "/airports",
    response_model=Envelope[RiskOverviewOut],
    summary="Latest risk indicator per airport",
)
def risk_overview(db: DbSession, response: Response) -> Envelope[RiskOverviewOut]:
    response.headers["Cache-Control"] = "public, max-age=30"
    rows = [
        dict(r)
        for r in db.execute(
            text(
                """SELECT DISTINCT ON (r.airport_iata) r.*, a.name
                   FROM risk_scores r JOIN airports a ON a.iata_code = r.airport_iata
                   ORDER BY r.airport_iata, r.computed_at DESC"""
            )
        ).mappings()
    ]
    items = sorted((RiskScoreOut.model_validate(r) for r in rows), key=lambda r: -r.score)
    latest = max((r.computed_at for r in items), default=None)
    counts = {
        c: sum(1 for r in items if r.category == c) for c in ("low", "moderate", "elevated", "high")
    }
    return Envelope(
        data=RiskOverviewOut(
            method_version=METHOD_VERSION,
            computed_at=latest,
            is_stale=latest is None or now_utc() - latest > dt.timedelta(minutes=30),
            category_counts=counts,
            airports=items,
            model=model_card(),
        ),
        meta=meta(),
    )


@router.get(
    "/airports/{code}", response_model=Envelope[AirportRiskOut], summary="Risk indicator history"
)
def airport_risk(
    airport: AirportDep,
    db: DbSession,
    response: Response,
    hours: Annotated[int, Query(ge=1, le=168)] = 48,
) -> Envelope[AirportRiskOut]:
    response.headers["Cache-Control"] = "public, max-age=30"
    since = now_utc() - dt.timedelta(hours=hours)
    latest = (
        db.execute(
            text(
                "SELECT r.*, a.name FROM risk_scores r JOIN airports a ON a.iata_code = r.airport_iata "
                "WHERE r.airport_iata = :a ORDER BY computed_at DESC LIMIT 1"
            ),
            {"a": airport.iata_code},
        )
        .mappings()
        .first()
    )
    history = db.execute(
        text(
            "SELECT computed_at, score, category, model_probability FROM risk_scores "
            "WHERE airport_iata = :a AND computed_at >= :s ORDER BY computed_at"
        ),
        {"a": airport.iata_code, "s": since},
    ).mappings()
    return Envelope(
        data=AirportRiskOut(
            latest=RiskScoreOut.model_validate(dict(latest)) if latest else None,
            history=[RiskPoint.model_validate(dict(h)) for h in history],
        ),
        meta=meta(),
    )
