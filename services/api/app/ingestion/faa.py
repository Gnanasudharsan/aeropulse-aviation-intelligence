"""Parsers for FAA NAS Status airport events.

Two upstream representations are supported:

* ``/api/airport-events`` (JSON, primary): list of per-airport objects with typed
  sub-objects (groundStop, groundDelay, airportClosure, freeForm, arrivalDelay,
  departureDelay, deicing, airportConfig).
* ``/api/airport-status-information`` (XML, fallback): legacy feed grouped by
  ``Delay_type``.

Both produce :class:`AdvisoryRecord` objects. Parsers are deliberately tolerant
of unknown/missing fields: anything unparseable is kept in ``details`` and the
record is still emitted if it has an airport and a type. Records missing either
are rejected and counted.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

ADVISORY_TYPES = (
    "ground_stop",
    "ground_delay_program",
    "airport_closure",
    "closure_notam",
    "arrival_delay",
    "departure_delay",
    "deicing",
)

DISRUPTION_TYPES = frozenset(
    {"ground_stop", "ground_delay_program", "airport_closure", "arrival_delay", "departure_delay"}
)

_JSON_KEY_TO_TYPE = {
    "groundStop": "ground_stop",
    "groundDelay": "ground_delay_program",
    "airportClosure": "airport_closure",
    "freeForm": "closure_notam",
    "arrivalDelay": "arrival_delay",
    "departureDelay": "departure_delay",
    "deicing": "deicing",
}

# NOTAM qualifiers that indicate the closure applies only to some operations.
_PARTIAL_MARKERS = re.compile(
    r"\b(EXC|EXCEPT|TO NON|NON SKED|TRANSIENT|PPR|MON|TUE|WED|THU|FRI|SAT|SUN|"
    r"GA ACFT|FOR|TWY|RWY)\b"
)


class ParseError(ValueError):
    pass


@dataclass(slots=True)
class AdvisoryRecord:
    airport_code: str
    advisory_type: str
    source_feed: str
    source_event_id: str | None = None
    scope: str = "full"
    reason: str | None = None
    text: str | None = None
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None
    source_updated_at: dt.datetime | None = None
    avg_delay_minutes: int | None = None
    min_delay_minutes: int | None = None
    max_delay_minutes: int | None = None
    trend: str | None = None
    probability_of_extension: str | None = None
    advisory_url: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def event_key(self) -> str:
        """Stable identity across polls.

        JSON events with an upstream id use it directly. Otherwise identity is
        (airport, type, start) — one GS/GDP/delay per airport/type/start.
        """
        if self.source_event_id:
            return f"faa:{self.advisory_type}:{self.source_event_id}"[:80]
        start = self.starts_at.strftime("%Y%m%dT%H%M") if self.starts_at else "na"
        basis = f"{self.airport_code}|{self.advisory_type}|{start}"
        if self.advisory_type in {"closure_notam", "airport_closure"}:
            basis += "|" + (self.text or self.reason or "")
        return f"faa:{self.advisory_type}:{hashlib.sha1(basis.encode()).hexdigest()[:20]}"  # noqa: S324

    @property
    def content_hash(self) -> str:
        """Hash of the fields whose change constitutes an 'update' event."""
        payload = {
            k: getattr(self, k)
            for k in (
                "scope",
                "reason",
                "text",
                "starts_at",
                "ends_at",
                "avg_delay_minutes",
                "min_delay_minutes",
                "max_delay_minutes",
                "trend",
                "probability_of_extension",
            )
        }
        blob = json.dumps(payload, default=str, sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()[:16]  # noqa: S324


@dataclass(slots=True)
class AirportConfigRecord:
    airport_code: str
    source_timestamp: dt.datetime
    arrival_runway_config: str | None
    departure_runway_config: str | None
    arrival_rate: int | None


@dataclass(slots=True)
class FaaParseResult:
    advisories: list[AdvisoryRecord] = field(default_factory=list)
    configs: list[AirportConfigRecord] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    published_at: dt.datetime | None = None
    airports_in_feed: int = 0


# --------------------------------------------------------------------------- helpers


def parse_iso(value: Any) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


_DURATION_RE = re.compile(r"(\d+)\s*(hour|hr|minute|min)", re.IGNORECASE)


def parse_duration_minutes(value: Any) -> int | None:
    """'1 hour and 15 minutes' -> 75, '45 minutes' -> 45, 30 -> 30, '16-30' -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    total, matched = 0, False
    for amount, unit in _DURATION_RE.findall(text):
        matched = True
        total += int(amount) * (60 if unit.lower().startswith("h") else 1)
    return total if matched else None


_DAILY_WINDOW_RE = re.compile(r"\bDLY\s+(\d{4})-(\d{4})\b")


def daily_window(text: str | None) -> tuple[str, str] | None:
    """'... CLSD DLY 0730-1415 ...' -> ('0730', '1415') (UTC, may wrap midnight)."""
    if not text:
        return None
    m = _DAILY_WINDOW_RE.search(text.upper())
    return (m.group(1), m.group(2)) if m else None


def in_daily_window(window: tuple[str, str], at: dt.datetime) -> bool:
    start = int(window[0][:2]) * 60 + int(window[0][2:])
    end = int(window[1][:2]) * 60 + int(window[1][2:])
    now = at.astimezone(dt.UTC)
    minute = now.hour * 60 + now.minute
    return start <= minute < end if start <= end else minute >= start or minute < end


def classify_notam_scope(text: str | None) -> str:
    """full | daily_window (full closure only inside a recurring UTC window) | partial."""
    if not text:
        return "full"
    upper = text.upper()
    if daily_window(upper):
        # A daily window combined with operation qualifiers is still partial.
        stripped = _DAILY_WINDOW_RE.sub("", upper)
        return "partial" if _PARTIAL_MARKERS.search(stripped) else "daily_window"
    return "partial" if _PARTIAL_MARKERS.search(upper) else "full"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# --------------------------------------------------------------------------- JSON


def parse_airport_events_json(text: str) -> FaaParseResult:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ParseError(f"expected a JSON array, got {type(data).__name__}")

    result = FaaParseResult(airports_in_feed=len(data))
    for entry in data:
        if not isinstance(entry, dict):
            result.rejected.append("non-object entry")
            continue
        airport = _str(entry.get("airportId"))
        if not airport:
            result.rejected.append("entry without airportId")
            continue
        airport = airport.upper()
        for key, adv_type in _JSON_KEY_TO_TYPE.items():
            for item in _as_list(entry.get(key)):
                if not isinstance(item, dict):
                    result.rejected.append(f"{airport}:{key} not an object")
                    continue
                result.advisories.append(_json_item_to_record(airport, adv_type, item))
        for cfg in _as_list(entry.get("airportConfig")):
            if isinstance(cfg, dict):
                ts = parse_iso(cfg.get("sourceTimeStamp")) or parse_iso(cfg.get("createdAt"))
                if ts:
                    rate = cfg.get("arrivalRate")
                    result.configs.append(
                        AirportConfigRecord(
                            airport_code=airport,
                            source_timestamp=ts,
                            arrival_runway_config=_str(cfg.get("arrivalRunwayConfig")),
                            departure_runway_config=_str(cfg.get("departureRunwayConfig")),
                            arrival_rate=int(rate) if isinstance(rate, int | float) else None,
                        )
                    )
    times = [a.source_updated_at for a in result.advisories if a.source_updated_at]
    result.published_at = max(times) if times else None
    return result


def _json_item_to_record(airport: str, adv_type: str, item: dict[str, Any]) -> AdvisoryRecord:
    rec = AdvisoryRecord(
        airport_code=airport,
        advisory_type=adv_type,
        source_feed="faa_json",
        source_event_id=_str(item.get("id")),
        starts_at=parse_iso(item.get("startTime")) or parse_iso(item.get("eventTime")),
        ends_at=parse_iso(item.get("endTime")),
        source_updated_at=parse_iso(item.get("updatedAt"))
        or parse_iso(item.get("updateTime"))
        or parse_iso(item.get("issuedDate"))
        or parse_iso(item.get("eventTime")),
        advisory_url=_str(item.get("advisoryUrl")),
    )
    if adv_type == "ground_stop":
        rec.reason = _str(item.get("impactingCondition"))
        rec.probability_of_extension = _str(item.get("probabilityOfExtension"))
        rec.details = {"included_facilities": item.get("includedFacilities")}
    elif adv_type == "ground_delay_program":
        rec.reason = _str(item.get("impactingCondition"))
        rec.avg_delay_minutes = parse_duration_minutes(item.get("avgDelay"))
        rec.max_delay_minutes = parse_duration_minutes(item.get("maxDelay"))
        rec.details = {
            "departure_scope": item.get("departureScope"),
            "included_facilities": item.get("includedFacilities"),
            "fuel_flow_advisory_delay_time": item.get("fuelFlowAdvisoryDelayTime"),
        }
    elif adv_type == "airport_closure":
        rec.text = _str(item.get("text"))
        rec.scope = "daily_window" if daily_window(rec.text) else "full"
    elif adv_type == "closure_notam":
        rec.text = _str(item.get("simpleText")) or _str(item.get("text"))
        rec.reason = _str(item.get("text"))
        rec.scope = classify_notam_scope(rec.text)
        rec.details = {"notam_number": item.get("notamNumber")}
    elif adv_type in {"arrival_delay", "departure_delay"}:
        rec.reason = _str(item.get("reason"))
        rec.trend = _str(item.get("trend"))
        avg = item.get("averageDelay")
        rec.avg_delay_minutes = parse_duration_minutes(avg)
        rec.min_delay_minutes = parse_duration_minutes(item.get("minDelay"))
        rec.max_delay_minutes = parse_duration_minutes(item.get("maxDelay"))
        rec.details = {"average_delay_text": avg}
    elif adv_type == "deicing":
        rec.reason = "De-icing in progress"
    window = daily_window(rec.text) if adv_type in {"airport_closure", "closure_notam"} else None
    if window:
        rec.details["daily_window_utc"] = list(window)
    rec.details = {k: v for k, v in rec.details.items() if v not in (None, "", [])}
    return rec


# --------------------------------------------------------------------------- XML


_XML_UPDATE_FMT = "%a %b %d %H:%M:%S %Y"
_XML_START_RE = re.compile(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+at\s+(\d{2}):(\d{2})\s*UTC", re.I)


def parse_xml_update_time(text: str | None) -> dt.datetime | None:
    if not text:
        return None
    try:
        return dt.datetime.strptime(text.replace(" GMT", "").strip(), _XML_UPDATE_FMT).replace(
            tzinfo=dt.UTC
        )
    except ValueError:
        return None


def parse_xml_month_day_time(text: str | None, reference: dt.datetime) -> dt.datetime | None:
    """'Nov 10 at 07:30 UTC.' -> datetime, choosing the year closest to ``reference``."""
    if not text:
        return None
    m = _XML_START_RE.search(text)
    if not m:
        return None
    mon, day, hh, mm = m.groups()
    candidates = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(
                dt.datetime.strptime(f"{year} {mon} {day} {hh}:{mm}", "%Y %b %d %H:%M").replace(
                    tzinfo=dt.UTC
                )
            )
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs((c - reference).total_seconds()))


def _t(el: ET.Element | None, tag: str) -> str | None:
    if el is None:
        return None
    child = el.find(tag)
    return _str(child.text) if child is not None else None


def parse_airport_status_xml(text: str, *, now: dt.datetime | None = None) -> FaaParseResult:
    now = now or dt.datetime.now(dt.UTC)
    if "<!ENTITY" in text:  # never expand entities from upstream
        raise ParseError("XML entity declarations are not accepted")
    try:
        root = ET.fromstring(text)  # noqa: S314 - entities rejected above
    except ET.ParseError as exc:
        raise ParseError(f"invalid XML: {exc}") from exc
    if root.tag != "AIRPORT_STATUS_INFORMATION":
        raise ParseError(f"unexpected root element {root.tag}")

    published = parse_xml_update_time(_t(root, "Update_Time"))
    result = FaaParseResult(published_at=published)
    ref = published or now
    airports: set[str] = set()

    for dtype in root.findall("Delay_type"):
        name = (_t(dtype, "Name") or "").lower()
        if "ground stop" in name:
            for prog in dtype.iter("Program"):
                rec = _xml_base(prog, "ground_stop", ref)
                if rec:
                    rec.reason = _t(prog, "Reason")
                    rec.ends_at = parse_xml_month_day_time(_t(prog, "End_Time"), ref)
                    rec.details = {"end_time_text": _t(prog, "End_Time")}
                    result.advisories.append(rec)
        elif "ground delay" in name:
            for gd in dtype.iter("Ground_Delay"):
                rec = _xml_base(gd, "ground_delay_program", ref)
                if rec:
                    rec.reason = _t(gd, "Reason")
                    rec.avg_delay_minutes = parse_duration_minutes(_t(gd, "Avg"))
                    rec.max_delay_minutes = parse_duration_minutes(_t(gd, "Max"))
                    result.advisories.append(rec)
        elif "closure" in name:
            for ap in dtype.iter("Airport"):
                rec = _xml_base(ap, "closure_notam", ref)
                if rec:
                    rec.text = _t(ap, "Reason")
                    rec.scope = classify_notam_scope(rec.text)
                    rec.starts_at = parse_xml_month_day_time(_t(ap, "Start"), ref)
                    rec.ends_at = parse_xml_month_day_time(_t(ap, "Reopen"), ref)
                    window = daily_window(rec.text)
                    if window:
                        rec.details = {"daily_window_utc": list(window)}
                    result.advisories.append(rec)
        elif "arrival/departure" in name or "general" in name:
            for delay in dtype.iter("Delay"):
                arpt = _t(delay, "ARPT")
                for ad in delay.findall("Arrival_Departure"):
                    kind = (ad.get("Type") or "").lower()
                    adv_type = "arrival_delay" if kind.startswith("arr") else "departure_delay"
                    if not arpt:
                        result.rejected.append("delay without ARPT")
                        continue
                    result.advisories.append(
                        AdvisoryRecord(
                            airport_code=arpt.upper(),
                            advisory_type=adv_type,
                            source_feed="faa_xml",
                            reason=_t(delay, "Reason"),
                            min_delay_minutes=parse_duration_minutes(_t(ad, "Min")),
                            max_delay_minutes=parse_duration_minutes(_t(ad, "Max")),
                            trend=_t(ad, "Trend"),
                        )
                    )
        elif "deicing" in name or "de-icing" in name:
            for ap in dtype.iter("Airport"):
                rec = _xml_base(ap, "deicing", ref)
                if rec:
                    result.advisories.append(rec)
        # Airspace flow programs are en-route, not airport events: intentionally skipped.

    for rec in result.advisories:
        airports.add(rec.airport_code)
        rec.source_updated_at = rec.source_updated_at or published
    result.airports_in_feed = len(airports)
    return result


def _xml_base(el: ET.Element, adv_type: str, ref: dt.datetime) -> AdvisoryRecord | None:
    arpt = _t(el, "ARPT")
    if not arpt:
        return None
    return AdvisoryRecord(airport_code=arpt.upper(), advisory_type=adv_type, source_feed="faa_xml")
