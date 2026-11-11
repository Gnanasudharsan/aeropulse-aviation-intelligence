from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from app.ingestion import faa

FIX = Path(__file__).parent / "fixtures"


def test_real_json_feed_parses_closures_and_configs() -> None:
    res = faa.parse_airport_events_json((FIX / "real_faa_airport_events.json").read_text())
    by_airport = {a.airport_code: a for a in res.advisories}
    assert set(by_airport) == {"LAS", "LAX", "SAN", "SNA"}
    assert not res.rejected
    las = by_airport["LAS"]
    assert las.advisory_type == "closure_notam"
    assert las.scope == "partial"  # "CLSD TO NON SKED TRANSIENT GA" is not a full closure
    assert las.starts_at == dt.datetime(2026, 10, 28, 19, 26, tzinfo=dt.UTC)
    assert las.event_key.startswith("faa:closure_notam:")
    sna = by_airport["SNA"]
    assert sna.advisory_type == "airport_closure"
    assert sna.scope == "daily_window"
    assert sna.details["daily_window_utc"] == ["0730", "1415"]
    assert {c.airport_code for c in res.configs} >= {"LAS", "LAX", "SAN"}


def test_synthetic_json_disruptions_and_rejections() -> None:
    res = faa.parse_airport_events_json((FIX / "synthetic_faa_disruptions.json").read_text())
    types = {(a.airport_code, a.advisory_type) for a in res.advisories}
    assert ("EWR", "ground_delay_program") in types
    assert ("EWR", "arrival_delay") in types
    assert ("SFO", "ground_stop") in types
    assert ("SFO", "departure_delay") in types
    assert ("ORD", "deicing") in types
    assert ("ORD", "closure_notam") in types
    gdp = next(a for a in res.advisories if a.advisory_type == "ground_delay_program")
    assert gdp.avg_delay_minutes == 57
    assert gdp.max_delay_minutes == 121
    assert gdp.source_event_id == "gdp-ewr-test-1"
    arr = next(a for a in res.advisories if a.advisory_type == "arrival_delay")
    assert arr.avg_delay_minutes == 75 and arr.trend == "Increasing"
    dep = next(a for a in res.advisories if a.advisory_type == "departure_delay")
    assert dep.avg_delay_minutes == 45
    ord_closure = next(a for a in res.advisories if a.advisory_type == "closure_notam")
    assert ord_closure.scope == "full"
    # entry without airportId + a non-object entry are rejected, not crashing the run
    assert len(res.rejected) == 2


def test_event_key_is_stable_and_content_hash_tracks_changes() -> None:
    text = (FIX / "synthetic_faa_disruptions.json").read_text()
    a = faa.parse_airport_events_json(text).advisories
    b = faa.parse_airport_events_json(text).advisories
    assert [x.event_key for x in a] == [x.event_key for x in b]
    rec = a[0]
    before = rec.content_hash
    rec.avg_delay_minutes = (rec.avg_delay_minutes or 0) + 10
    assert rec.content_hash != before


@pytest.mark.parametrize(
    "payload",
    ["", "{not json", '{"airportId": "JFK"}', "null"],
)
def test_malformed_json_raises_parse_error(payload: str) -> None:
    with pytest.raises(faa.ParseError):
        faa.parse_airport_events_json(payload)


def test_real_xml_feed() -> None:
    res = faa.parse_airport_status_xml((FIX / "real_faa_status.xml").read_text())
    assert res.published_at == dt.datetime(2026, 11, 11, 4, 12, 51, tzinfo=dt.UTC)
    assert {a.airport_code for a in res.advisories} == {"SNA", "LAX", "SAN", "LAS"}
    sna = next(a for a in res.advisories if a.airport_code == "SNA")
    assert sna.starts_at == dt.datetime(2026, 11, 10, 7, 30, tzinfo=dt.UTC)
    assert sna.ends_at == dt.datetime(2026, 11, 21, 14, 15, tzinfo=dt.UTC)


def test_xml_year_inference_across_new_year() -> None:
    res = faa.parse_airport_status_xml((FIX / "real_faa_status.xml").read_text())
    san = next(a for a in res.advisories if a.airport_code == "SAN")
    # "Reopen Jan 01" published in Nov 2026 must resolve to 2027, not 2026.
    assert san.ends_at == dt.datetime(2027, 1, 1, 8, 0, tzinfo=dt.UTC)


def test_synthetic_xml_disruptions() -> None:
    res = faa.parse_airport_status_xml((FIX / "synthetic_faa_status.xml").read_text())
    kinds = {(a.airport_code, a.advisory_type) for a in res.advisories}
    assert kinds == {
        ("SFO", "ground_stop"),
        ("EWR", "ground_delay_program"),
        ("BOS", "departure_delay"),
        ("SNA", "closure_notam"),
    }
    bos = next(a for a in res.advisories if a.airport_code == "BOS")
    assert (bos.min_delay_minutes, bos.max_delay_minutes, bos.trend) == (16, 30, "Increasing")
    assert all(a.source_feed == "faa_xml" for a in res.advisories)


@pytest.mark.parametrize(
    "payload",
    ["", "<oops", "<OTHER_ROOT/>", '<!DOCTYPE x [<!ENTITY a "b">]><AIRPORT_STATUS_INFORMATION/>'],
)
def test_malformed_or_unsafe_xml_rejected(payload: str) -> None:
    with pytest.raises(faa.ParseError):
        faa.parse_airport_status_xml(payload)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1 hour and 15 minutes", 75),
        ("45 minutes", 45),
        ("2 hours", 120),
        (30, 30),
        ("30", 30),
        ("", None),
        (None, None),
        ("unknown", None),
        (True, None),
    ],
)
def test_parse_duration_minutes(value: object, expected: int | None) -> None:
    assert faa.parse_duration_minutes(value) == expected


@pytest.mark.parametrize(
    ("text", "scope"),
    [
        ("!LAS 10/160 LAS AD AP CLSD TO NON SKED TRANSIENT GA ACFT EXC 24HR PPR", "partial"),
        ("!SNA 11/008 SNA AD AP CLSD DLY 0730-1415 2611100730-2611211415", "daily_window"),
        ("!XYZ 11/001 XYZ AD AP CLSD DLY 0400-0600 EXC PPR", "partial"),
        ("!ORD 11/001 ORD AD AP CLSD 2611110500-2611110900", "full"),
        (None, "full"),
    ],
)
def test_notam_scope_classification(text: str | None, scope: str) -> None:
    assert faa.classify_notam_scope(text) == scope


@pytest.mark.parametrize(
    ("window", "hhmm", "inside"),
    [
        (("0730", "1415"), (8, 0), True),
        (("0730", "1415"), (14, 15), False),
        (("0730", "1415"), (4, 0), False),
        (("2200", "0600"), (23, 30), True),  # wraps midnight
        (("2200", "0600"), (5, 59), True),
        (("2200", "0600"), (12, 0), False),
    ],
)
def test_in_daily_window(window: tuple[str, str], hhmm: tuple[int, int], inside: bool) -> None:
    at = dt.datetime(2026, 11, 11, *hhmm, tzinfo=dt.UTC)
    assert faa.in_daily_window(window, at) is inside
