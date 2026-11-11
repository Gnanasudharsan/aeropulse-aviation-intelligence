"""Historical BTS performance analytics (separate from live operations).

Every rate is recomputed from additive sums at the requested grain (never an average of
averages). Definitions: analytics/metric_definitions/README.md.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import AirportDep, DbSession, meta
from app.schemas import Envelope, Model

router = APIRouter(tags=["analytics"])

Direction = Literal["arrival", "departure"]

RATES = """
    sum(flights)::int                                                   AS flights,
    sum(cancelled)::int                                                 AS cancelled,
    sum(diverted)::int                                                  AS diverted,
    sum(delayed_15)::int                                                AS delayed_15,
    round(sum(ontime_num)::numeric / nullif(sum(ontime_den), 0), 4)::float     AS ontime_rate,
    round(sum(cancelled)::numeric / nullif(sum(flights), 0), 4)::float         AS cancel_rate,
    round(sum(delay_sum_min)::numeric / nullif(sum(ontime_den), 0), 2)::float  AS avg_delay_min
"""


class PerfRow(Model):
    flights: int
    cancelled: int
    diverted: int
    delayed_15: int
    ontime_rate: float | None
    cancel_rate: float | None
    avg_delay_min: float | None


class MonthRow(PerfRow):
    month: dt.date


class AirportRank(PerfRow):
    airport: str
    name: str
    rank_ontime: int


class BucketRow(Model):
    key: str
    value: float


class DowRow(PerfRow):
    iso_dow: int


class HourRow(PerfRow):
    hour_local: int


class AirportMonthCell(Model):
    airport: str
    month: dt.date
    flights: int
    ontime_rate: float | None
    avg_delay_min: float | None


class CarrierRow(PerfRow):
    carrier_code: str
    carrier_name: str


class Coverage(Model):
    first_month: dt.date | None
    last_month: dt.date | None
    months_loaded: int
    selected_start: dt.date | None
    selected_end: dt.date | None
    source: str = "BTS Reporting Carrier On-Time Performance (U.S. DOT)"
    lag_note: str = "BTS publishes monthly with a ~2-3 month lag."


class Comparison(Model):
    ontime_rate: float | None
    cancel_rate: float | None
    avg_delay_min: float | None
    flights: int | None


class AnalyticsOut(Model):
    available: bool
    direction: Direction
    coverage: Coverage
    totals: PerfRow | None
    previous_year: Comparison | None
    network: Comparison | None = None
    monthly: list[MonthRow]
    airports: list[AirportRank]
    causes_minutes: list[BucketRow]
    cancellation_causes: list[BucketRow]
    delay_distribution: list[BucketRow]
    day_of_week: list[DowRow]
    hourly: list[HourRow]
    carriers: list[CarrierRow]
    airport_monthly: list[AirportMonthCell] = []


def _coverage(db: Session) -> tuple[dt.date | None, dt.date | None, int]:
    row = db.execute(
        text("SELECT min(year_month), max(year_month), count(*) FROM historical_loads")
    ).one()
    return row[0], row[1], int(row[2])


def _month_bounds(
    start: str | None, end: str | None, first: dt.date, last: dt.date
) -> tuple[dt.date, dt.date]:
    def parse(v: str) -> dt.date:
        try:
            y, m = map(int, v.split("-"))
            return dt.date(y, m, 1)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid month '{v}', expected YYYY-MM"
            ) from exc

    s = (
        parse(start)
        if start
        else max(first, dt.date(last.year - (last.month < 12), last.month % 12 + 1, 1))
    )
    e = parse(end) if end else last
    if s > e:
        raise HTTPException(status_code=422, detail="'start' must not be after 'end'")
    return max(s, first), min(e, last)


def _next_month(d: dt.date) -> dt.date:
    return dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _rows(db: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(text(sql), params).mappings()]


def build_analytics(
    db: Session, *, airport: str | None, start: str | None, end: str | None, direction: Direction
) -> AnalyticsOut:
    first, last, n = _coverage(db)
    if not first or not last:
        return AnalyticsOut(
            available=False,
            direction=direction,
            coverage=Coverage(
                first_month=None,
                last_month=None,
                months_loaded=0,
                selected_start=None,
                selected_end=None,
            ),
            totals=None,
            previous_year=None,
            monthly=[],
            airports=[],
            causes_minutes=[],
            cancellation_causes=[],
            delay_distribution=[],
            day_of_week=[],
            hourly=[],
            carriers=[],
            airport_monthly=[],
        )
    s, e = _month_bounds(start, end, first, last)
    p: dict[str, Any] = {"s": s, "e": _next_month(e), "dir": direction, "ap": airport}
    ap_filter = "AND airport_iata = :ap" if airport else ""
    daily = f"FROM airport_performance_daily WHERE direction = :dir AND flight_date >= :s AND flight_date < :e {ap_filter}"

    totals_row = _rows(
        db,
        f"SELECT {RATES}, sum(carrier_delay_min) c, sum(weather_delay_min) w, sum(nas_delay_min) n, "
        f"sum(security_delay_min) sec, sum(late_aircraft_delay_min) la, sum(cancel_carrier) cc, "
        f"sum(cancel_weather) cw, sum(cancel_nas) cn, sum(cancel_security) cs, "
        f"sum(bucket_early) b0, sum(bucket_0_14) b1, sum(bucket_15_29) b2, sum(bucket_30_59) b3, "
        f"sum(bucket_60_119) b4, sum(bucket_120_plus) b5 {daily}",
        p,
    )[0]
    totals = PerfRow.model_validate(totals_row) if totals_row["flights"] else None

    py = {
        "s": dt.date(s.year - 1, s.month, 1),
        "e": dt.date(_next_month(e).year - 1, _next_month(e).month, 1),
    }
    prev = None
    if py["s"] >= first:
        r = _rows(
            db,
            f"SELECT {RATES} FROM airport_performance_daily WHERE direction = :dir "
            f"AND flight_date >= :s AND flight_date < :e {ap_filter}",
            {**p, **py},
        )[0]
        if r["flights"]:
            prev = Comparison(
                **{k: r[k] for k in ("ontime_rate", "cancel_rate", "avg_delay_min", "flights")}
            )

    network = None
    if airport:
        r = _rows(
            db,
            f"SELECT {RATES} FROM airport_performance_daily WHERE direction = :dir "
            "AND flight_date >= :s AND flight_date < :e",
            p,
        )[0]
        network = Comparison(
            **{k: r[k] for k in ("ontime_rate", "cancel_rate", "avg_delay_min", "flights")}
        )

    monthly = [
        MonthRow.model_validate(r)
        for r in _rows(
            db,
            f"SELECT date_trunc('month', flight_date)::date AS month, {RATES} {daily} GROUP BY 1 ORDER BY 1",
            p,
        )
    ]
    airports = [
        AirportRank.model_validate(r)
        for r in _rows(
            db,
            f"""SELECT d.airport_iata AS airport, a.name, {RATES},
                       rank() OVER (ORDER BY sum(ontime_num)::numeric / nullif(sum(ontime_den), 0) DESC NULLS LAST)::int
                           AS rank_ontime
                FROM airport_performance_daily d JOIN airports a ON a.iata_code = d.airport_iata
                WHERE direction = :dir AND flight_date >= :s AND flight_date < :e
                GROUP BY 1, 2 ORDER BY rank_ontime""",
            p,
        )
    ]
    dow = [
        DowRow.model_validate(r)
        for r in _rows(
            db,
            f"SELECT extract(isodow FROM flight_date)::int AS iso_dow, {RATES} {daily} GROUP BY 1 ORDER BY 1",
            p,
        )
    ]
    hourly = [
        HourRow.model_validate(r)
        for r in _rows(
            db,
            f"""SELECT hour_local, {RATES} FROM airport_performance_hourly
                WHERE direction = :dir AND year_month >= :s AND year_month < :e {ap_filter}
                GROUP BY 1 ORDER BY 1""",
            p,
        )
    ]
    carriers = [
        CarrierRow.model_validate(r)
        for r in _rows(
            db,
            f"""SELECT c.carrier_code, coalesce(k.carrier_name, c.carrier_code) AS carrier_name, {RATES}
                FROM carrier_performance_monthly c LEFT JOIN carriers k USING (carrier_code)
                WHERE direction = :dir AND year_month >= :s AND year_month < :e {ap_filter}
                GROUP BY 1, 2 ORDER BY flights DESC""",
            p,
        )
    ]
    grid: list[AirportMonthCell] = []
    if not airport:
        grid = [
            AirportMonthCell.model_validate(r)
            for r in _rows(
                db,
                f"""SELECT airport_iata AS airport, date_trunc('month', flight_date)::date AS month, {RATES}
                    FROM airport_performance_daily
                    WHERE direction = :dir AND flight_date >= :s AND flight_date < :e
                    GROUP BY 1, 2 ORDER BY 1, 2""",
                p,
            )
        ]
    t = totals_row
    causes = [
        ("Late-arriving aircraft", t["la"]),
        ("Air carrier", t["c"]),
        ("National Airspace System", t["n"]),
        ("Weather", t["w"]),
        ("Security", t["sec"]),
    ]
    cancels = [
        ("Carrier", t["cc"]),
        ("Weather", t["cw"]),
        ("National Airspace System", t["cn"]),
        ("Security", t["cs"]),
    ]
    dist = [
        ("Early", t["b0"]),
        ("0-14 min", t["b1"]),
        ("15-29 min", t["b2"]),
        ("30-59 min", t["b3"]),
        ("60-119 min", t["b4"]),
        ("120+ min", t["b5"]),
    ]

    def as_rows(pairs: list[tuple[str, Any]]) -> list[BucketRow]:
        return [BucketRow(key=k, value=float(v or 0)) for k, v in pairs]

    return AnalyticsOut(
        available=True,
        direction=direction,
        coverage=Coverage(
            first_month=first, last_month=last, months_loaded=n, selected_start=s, selected_end=e
        ),
        totals=totals,
        previous_year=prev,
        network=network,
        monthly=monthly,
        airports=airports,
        causes_minutes=as_rows(causes),
        cancellation_causes=as_rows(cancels),
        delay_distribution=as_rows(dist),
        day_of_week=dow,
        hourly=hourly,
        carriers=carriers,
        airport_monthly=grid,
    )


MonthParam = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")]


@router.get(
    "/analytics/overview",
    response_model=Envelope[AnalyticsOut],
    summary="Historical performance (BTS)",
)
def overview(
    db: DbSession,
    response: Response,
    start: MonthParam = None,
    end: MonthParam = None,
    direction: Direction = "arrival",
) -> Envelope[AnalyticsOut]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return Envelope(
        data=build_analytics(db, airport=None, start=start, end=end, direction=direction),
        meta=meta(),
    )


@router.get(
    "/airports/{code}/history",
    response_model=Envelope[AnalyticsOut],
    tags=["airports"],
    summary="Historical performance for one airport (BTS)",
)
def airport_history(
    airport: AirportDep,
    db: DbSession,
    response: Response,
    start: MonthParam = None,
    end: MonthParam = None,
    direction: Direction = "arrival",
) -> Envelope[AnalyticsOut]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    data = build_analytics(db, airport=airport.iata_code, start=start, end=end, direction=direction)
    return Envelope(data=data, meta=meta())
