"""Registry of upstream sources and their freshness thresholds (seconds).

Thresholds implement analytics/metric_definitions/README.md § Data freshness.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceSpec:
    key: str
    display_name: str
    url: str
    expected_interval_s: int
    healthy_s: int
    delayed_s: int
    stale_s: int
    limitations: str


H = 3600
SOURCES: dict[str, SourceSpec] = {
    "faa_nas_status": SourceSpec(
        key="faa_nas_status",
        display_name="FAA NAS Status — airport events",
        url="https://nasstatus.faa.gov/",
        expected_interval_s=300,
        healthy_s=600,
        delayed_s=1800,
        stale_s=6 * H,
        limitations=(
            "Lists only airports with active events; absence means 'nothing reported', not "
            "'verified normal'. Endpoint is public but not a formally versioned API."
        ),
    ),
    "awc_metar": SourceSpec(
        key="awc_metar",
        display_name="NOAA AWC — METAR observations",
        url="https://aviationweather.gov/data/api/",
        expected_interval_s=600,
        healthy_s=1200,
        delayed_s=H,
        stale_s=6 * H,
        limitations=(
            "Routine METARs are issued hourly (plus SPECI when conditions change); a newer "
            "poll does not imply a newer observation."
        ),
    ),
    "awc_taf": SourceSpec(
        key="awc_taf",
        display_name="NOAA AWC — TAF forecasts",
        url="https://aviationweather.gov/data/api/",
        expected_interval_s=1800,
        healthy_s=H,
        delayed_s=3 * H,
        stale_s=12 * H,
        limitations="TAFs are forecasts (issued ~every 6 h, amended as needed), not observations.",
    ),
    "bts_ontime": SourceSpec(
        key="bts_ontime",
        display_name="BTS — Reporting Carrier On-Time Performance",
        url="https://www.transtats.bts.gov/",
        expected_interval_s=30 * 24 * H,
        healthy_s=120 * 24 * H,
        delayed_s=180 * 24 * H,
        stale_s=365 * 24 * H,
        limitations=(
            "Monthly with a ~2-3 month publication lag; covers reporting carriers' scheduled "
            "domestic flights only. Freshness is measured from the end of the latest data month."
        ),
    ),
}

# Bronze payload source identifiers (more granular than SOURCES).
FEED_FAA_JSON = "faa_airport_events"
FEED_FAA_XML = "faa_status_xml"
FEED_METAR = "awc_metar"
FEED_TAF = "awc_taf"
