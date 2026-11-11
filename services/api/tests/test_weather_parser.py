from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion import weather as wx

FIX = Path(__file__).parent / "fixtures"


def test_real_metars_parse() -> None:
    out = wx.parse_metars((FIX / "real_awc_metar.json").read_text())
    assert out.records and not out.rejected
    jfk = next(r for r in out.records if r.station_icao == "KJFK")
    assert jfk.observed_at.tzinfo == dt.UTC
    assert jfk.flight_category in {"VFR", "MVFR", "IFR", "LIFR"}
    assert jfk.flight_category_source == "awc"
    assert jfk.raw_text.startswith(("METAR KJFK", "SPECI KJFK"))
    assert len(jfk.raw_hash) == 16
    # receipt time is a different clock than observation time
    assert jfk.source_published_at is None or jfk.source_published_at >= jfk.observed_at


def test_metar_missing_timestamp_and_bad_ids_rejected() -> None:
    payload = json.dumps(
        [
            {"icaoId": "KJFK", "rawOb": "METAR KJFK ...", "obsTime": 0},
            {"icaoId": "K!", "rawOb": "x", "obsTime": 1794369060},
            {"icaoId": "KBOS", "obsTime": 1794369060},  # no rawOb
            {
                "icaoId": "KORD",
                "rawOb": "METAR KORD 110351Z",
                "obsTime": 1794369060,
                "visib": "1/2",
                "clouds": [{"cover": "OVC", "base": 300}],
            },
        ]
    )
    out = wx.parse_metars(payload)
    assert len(out.rejected) == 3
    (rec,) = out.records
    assert rec.visibility_sm == Decimal("0.5")
    assert rec.ceiling_ft == 300
    assert rec.flight_category == "LIFR" and rec.flight_category_source == "derived"


def test_empty_body_means_no_records() -> None:
    assert wx.parse_metars("").records == []


@pytest.mark.parametrize("payload", ["{bad", '{"a": 1}'])
def test_malformed_payload_raises(payload: str) -> None:
    with pytest.raises(wx.ParseError):
        wx.parse_metars(payload)


@pytest.mark.parametrize(
    ("value", "miles", "lower"),
    [
        ("10+", Decimal("10"), True),
        (10, Decimal("10"), False),
        ("1/2", Decimal("0.5"), False),
        ("1 1/2", Decimal("1.5"), False),
        ("P6SM", Decimal("6"), True),
        ("6+", Decimal("6"), True),
        (None, None, False),
        ("garbage", None, False),
    ],
)
def test_parse_visibility(value: object, miles: Decimal | None, lower: bool) -> None:
    got, _text, is_lower = wx.parse_visibility(value)
    assert got == miles
    assert is_lower is lower


@pytest.mark.parametrize(
    ("ceiling", "vis", "cat"),
    [
        (None, Decimal("10"), "VFR"),
        (3500, Decimal("6"), "VFR"),
        (3000, Decimal("10"), "MVFR"),
        (5000, Decimal("4"), "MVFR"),
        (800, Decimal("10"), "IFR"),
        (5000, Decimal("2"), "IFR"),
        (400, Decimal("10"), "LIFR"),
        (5000, Decimal("0.5"), "LIFR"),
        (None, None, None),
    ],
)
def test_flight_category_rules(ceiling: int | None, vis: Decimal | None, cat: str | None) -> None:
    assert wx.derive_flight_category(ceiling, vis) == cat


def test_ceiling_ignores_few_and_sct() -> None:
    layers = [
        {"cover": "FEW", "base": 500},
        {"cover": "SCT", "base": 900},
        {"cover": "BKN", "base": 2500},
    ]
    assert wx.ceiling_from_layers(layers) == 2500


def test_real_tafs_parse_periods() -> None:
    out = wx.parse_tafs((FIX / "real_awc_taf.json").read_text())
    assert out.records and not out.rejected
    taf = out.records[0]
    assert taf.valid_to > taf.valid_from
    assert taf.periods and taf.periods[0].seq == 0
    assert all(p.time_to > p.time_from for p in taf.periods)


def test_taf_missing_issue_time_rejected() -> None:
    out = wx.parse_tafs(json.dumps([{"icaoId": "KJFK", "rawTAF": "TAF KJFK", "validTimeFrom": 1}]))
    assert out.records == [] and len(out.rejected) == 1
