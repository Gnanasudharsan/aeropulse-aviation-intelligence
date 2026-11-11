"""Parsers for NOAA Aviation Weather Center METAR and TAF JSON."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class ParseError(ValueError):
    pass


CEILING_COVERS = {"BKN", "OVC", "OVX"}


# --------------------------------------------------------------------------- primitives


def parse_visibility(value: Any) -> tuple[Decimal | None, str | None, bool]:
    """AWC visibility -> (statute miles, original text, is_lower_bound).

    Examples: 10 -> 10; "10+" -> 10 (lower bound); "1/2" -> 0.5; "1 1/2" -> 1.5; "P6SM" -> 6+.
    """
    if value is None or value == "":
        return None, None, False
    text = str(value).strip()
    lower_bound = text.endswith("+") or text.upper().startswith("P")
    cleaned = text.rstrip("+").upper().removeprefix("P").removesuffix("SM").strip()
    try:
        total = sum((Fraction(part) for part in cleaned.split()), Fraction(0))
        return Decimal(str(round(float(total), 2))), text, lower_bound
    except (ValueError, ZeroDivisionError, InvalidOperation):
        return None, text, False


def ceiling_from_layers(layers: list[dict[str, Any]], vert_vis: Any = None) -> int | None:
    bases = [
        int(layer["base"])
        for layer in layers
        if isinstance(layer, dict)
        and str(layer.get("cover", "")).upper() in CEILING_COVERS
        and isinstance(layer.get("base"), int | float)
    ]
    if isinstance(vert_vis, int | float):
        bases.append(int(vert_vis) * (100 if vert_vis < 100 else 1))
    return min(bases) if bases else None


def derive_flight_category(ceiling_ft: int | None, visibility_sm: Decimal | None) -> str | None:
    """FAA flight category from ceiling (ft AGL) and visibility (SM)."""
    if ceiling_ft is None and visibility_sm is None:
        return None
    c = ceiling_ft if ceiling_ft is not None else 100_000
    v = float(visibility_sm) if visibility_sm is not None else 99.0
    if c < 500 or v < 1:
        return "LIFR"
    if c < 1000 or v < 3:
        return "IFR"
    if c <= 3000 or v <= 5:
        return "MVFR"
    return "VFR"


def epoch_to_dt(value: Any) -> dt.datetime | None:
    if isinstance(value, int | float) and value > 0:
        return dt.datetime.fromtimestamp(value, tz=dt.UTC)
    return None


def iso_to_dt(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    return None


# --------------------------------------------------------------------------- METAR


class _AwcMetar(BaseModel):
    """Upstream contract (only fields we rely on). Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    icaoId: str
    obsTime: int
    rawOb: str
    receiptTime: str | None = None
    reportTime: str | None = None
    metarType: str | None = "METAR"
    temp: float | None = None
    dewp: float | None = None
    wdir: int | str | None = None
    wspd: int | None = None
    wgst: int | None = None
    visib: str | float | int | None = None
    altim: float | None = None
    slp: float | None = None
    wxString: str | None = None
    clouds: list[dict[str, Any]] = []
    vertVis: int | None = None
    fltCat: str | None = None

    @field_validator("icaoId")
    @classmethod
    def _icao(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 4 or not v.isalnum():
            raise ValueError(f"invalid ICAO id {v!r}")
        return v

    @field_validator("obsTime")
    @classmethod
    def _obs(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("obsTime missing")
        return v


@dataclass(slots=True)
class MetarRecord:
    station_icao: str
    observed_at: dt.datetime
    raw_text: str
    raw_hash: str
    source_published_at: dt.datetime | None
    report_time: dt.datetime | None
    metar_type: str
    temperature_c: float | None
    dewpoint_c: float | None
    wind_dir_deg: int | None
    wind_dir_variable: bool
    wind_speed_kt: int | None
    wind_gust_kt: int | None
    visibility_sm: Decimal | None
    visibility_text: str | None
    visibility_is_lower_bound: bool
    altimeter_hpa: float | None
    sea_level_pressure_hpa: float | None
    ceiling_ft: int | None
    cloud_layers: list[dict[str, Any]]
    wx_string: str | None
    flight_category: str | None
    flight_category_source: str


@dataclass(slots=True)
class ParseOutcome[T]:
    records: list[T] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def _load_list(text: str) -> list[Any]:
    if not text.strip():
        return []  # AWC returns an empty body when no stations match
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ParseError(f"expected JSON array, got {type(data).__name__}")
    return data


def parse_metars(text: str) -> ParseOutcome[MetarRecord]:
    out: ParseOutcome[MetarRecord] = ParseOutcome()
    for item in _load_list(text):
        try:
            m = _AwcMetar.model_validate(item)
        except ValidationError as exc:
            ident = item.get("icaoId", "?") if isinstance(item, dict) else "?"
            out.rejected.append(f"{ident}: {exc.errors()[0]['msg']}")
            continue
        vis, vis_text, lower = parse_visibility(m.visib)
        layers = [
            {"cover": c.get("cover"), "base_ft": c.get("base")}
            for c in m.clouds
            if isinstance(c, dict)
        ]
        ceiling = ceiling_from_layers(m.clouds, m.vertVis)
        cat = (m.fltCat or "").upper() or None
        cat_source = "awc"
        if cat not in {"VFR", "MVFR", "IFR", "LIFR"}:
            cat, cat_source = derive_flight_category(ceiling, vis), "derived"
        variable = isinstance(m.wdir, str) and m.wdir.upper() == "VRB"
        out.records.append(
            MetarRecord(
                station_icao=m.icaoId,
                observed_at=dt.datetime.fromtimestamp(m.obsTime, tz=dt.UTC),
                raw_text=m.rawOb.strip(),
                raw_hash=short_hash(m.rawOb.strip()),
                source_published_at=iso_to_dt(m.receiptTime),
                report_time=iso_to_dt(m.reportTime),
                metar_type=(m.metarType or "METAR")[:8],
                temperature_c=m.temp,
                dewpoint_c=m.dewp,
                wind_dir_deg=m.wdir if isinstance(m.wdir, int) else None,
                wind_dir_variable=variable,
                wind_speed_kt=m.wspd,
                wind_gust_kt=m.wgst,
                visibility_sm=vis,
                visibility_text=vis_text,
                visibility_is_lower_bound=lower,
                altimeter_hpa=m.altim,
                sea_level_pressure_hpa=m.slp,
                ceiling_ft=ceiling,
                cloud_layers=layers,
                wx_string=m.wxString,
                flight_category=cat,
                flight_category_source=cat_source,
            )
        )
    return out


# --------------------------------------------------------------------------- TAF


@dataclass(slots=True)
class TafPeriodRecord:
    seq: int
    time_from: dt.datetime
    time_to: dt.datetime
    change_indicator: str | None
    probability: int | None
    wind_dir_deg: int | None
    wind_speed_kt: int | None
    wind_gust_kt: int | None
    visibility_sm: Decimal | None
    visibility_text: str | None
    wx_string: str | None
    ceiling_ft: int | None
    cloud_layers: list[dict[str, Any]]
    flight_category: str | None


@dataclass(slots=True)
class TafRecord:
    station_icao: str
    issued_at: dt.datetime
    bulletin_at: dt.datetime | None
    valid_from: dt.datetime
    valid_to: dt.datetime
    raw_text: str
    raw_hash: str
    is_amendment: bool
    periods: list[TafPeriodRecord]


def parse_tafs(text: str) -> ParseOutcome[TafRecord]:
    out: ParseOutcome[TafRecord] = ParseOutcome()
    for item in _load_list(text):
        if not isinstance(item, dict):
            out.rejected.append("non-object TAF")
            continue
        icao = str(item.get("icaoId", "")).upper()
        issued = iso_to_dt(item.get("issueTime"))
        vf, vt = epoch_to_dt(item.get("validTimeFrom")), epoch_to_dt(item.get("validTimeTo"))
        raw = str(item.get("rawTAF") or "").strip()
        if len(icao) != 4 or not issued or not vf or not vt or not raw:
            out.rejected.append(f"{icao or '?'}: missing id/issueTime/validity/raw")
            continue
        periods: list[TafPeriodRecord] = []
        for seq, p in enumerate(item.get("fcsts") or []):
            if not isinstance(p, dict):
                continue
            tf, tt = epoch_to_dt(p.get("timeFrom")), epoch_to_dt(p.get("timeTo"))
            if not tf or not tt:
                continue
            vis, vis_text, _ = parse_visibility(p.get("visib"))
            clouds = [c for c in (p.get("clouds") or []) if isinstance(c, dict)]
            ceiling = ceiling_from_layers(clouds, p.get("vertVis"))
            periods.append(
                TafPeriodRecord(
                    seq=seq,
                    time_from=tf,
                    time_to=tt,
                    change_indicator=p.get("fcstChange"),
                    probability=_int_or_none(p.get("probability")),
                    wind_dir_deg=_int_or_none(p.get("wdir")),
                    wind_speed_kt=_int_or_none(p.get("wspd")),
                    wind_gust_kt=_int_or_none(p.get("wgst")),
                    visibility_sm=vis,
                    visibility_text=vis_text,
                    wx_string=p.get("wxString"),
                    ceiling_ft=ceiling,
                    cloud_layers=[
                        {"cover": c.get("cover"), "base_ft": c.get("base")} for c in clouds
                    ],
                    flight_category=derive_flight_category(ceiling, vis),
                )
            )
        remarks = str(item.get("remarks") or "")
        out.records.append(
            TafRecord(
                station_icao=icao,
                issued_at=issued,
                bulletin_at=iso_to_dt(item.get("bulletinTime")),
                valid_from=vf,
                valid_to=vt,
                raw_text=raw,
                raw_hash=short_hash(raw),
                is_amendment="AMD" in remarks.upper() or raw.upper().startswith("TAF AMD"),
                periods=periods,
            )
        )
    return out
