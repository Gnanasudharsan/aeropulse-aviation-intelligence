"""Generate the AeroPulse report in Power BI's enhanced report format (PBIR).

Every file declares the official Microsoft JSON schema it follows and is validated against
those schemas by ``validate_pbip.py``. Layout: 1280 x 720 pages, a 16 px grid, dark AeroPulse
theme (registered custom theme). Visual specification: docs/dashboards/powerbi-report.md.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NS = uuid.UUID("2b0c9d3e-61f5-4b8e-9a0a-aeb0a1c0beef")
BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report"
SCHEMA = {
    "pbir": f"{BASE}/definitionProperties/2.0.0/schema.json",
    "report": f"{BASE}/definition/report/3.3.0/schema.json",
    "version": f"{BASE}/definition/versionMetadata/1.0.0/schema.json",
    "pages": f"{BASE}/definition/pagesMetadata/1.1.0/schema.json",
    "page": f"{BASE}/definition/page/2.1.0/schema.json",
    "visual": f"{BASE}/definition/visualContainer/2.13.0/schema.json",
}
VERSIONS = {"report": "3.3.0", "page": "2.1.0", "visual": "2.13.0"}
F = "FactAirportDaily"
THEME_FILE = "AeroPulse-dark.json"

THEME: dict[str, Any] = {
    "name": "AeroPulse Dark",
    "dataColors": ["#1A9DB2", "#D9733F", "#9085E9", "#AA880A", "#D55181", "#4C9A2A", "#3ED4E8", "#49DBAA"],
    "background": "#0B1220",
    "secondaryBackground": "#16263E",
    "foreground": "#F3F8FF",
    "foregroundNeutralSecondary": "#A8BED3",
    "tableAccent": "#3ED4E8",
    "good": "#49DBAA",
    "neutral": "#FFB454",
    "bad": "#F27989",
    "maximum": "#3ED4E8",
    "center": "#1C3050",
    "minimum": "#7A3550",
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#F3F8FF"},
        "header": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#F3F8FF"},
        "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#A8BED3"},
        "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 26, "color": "#F3F8FF"},
    },
    "visualStyles": {
        "*": {
            "*": {
                "background": [{"show": True, "color": {"solid": {"color": "#16263E"}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": "#24395A"}}, "radius": 10}],
                "title": [{"show": True, "fontColor": {"solid": {"color": "#F3F8FF"}}, "fontSize": 11}],
                "dropShadow": [{"show": False}],
            }
        },
        "page": {
            "*": {
                "background": [{"color": {"solid": {"color": "#0B1220"}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": "#0B1220"}}, "transparency": 0}],
            }
        },
    },
}


def vid(*parts: str) -> str:
    """Stable 20-character identifiers (Power BI uses hex names)."""
    return uuid.uuid5(NS, "/".join(parts)).hex[:20]


def lit(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": value}}}


def measure(entity: str, prop: str) -> dict[str, Any]:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def column(entity: str, prop: str) -> dict[str, Any]:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


@dataclass
class Field:
    entity: str
    prop: str
    kind: str = "measure"  # measure | column

    @property
    def expr(self) -> dict[str, Any]:
        return measure(self.entity, self.prop) if self.kind == "measure" else column(self.entity, self.prop)

    def projection(self) -> dict[str, Any]:
        return {"field": self.expr, "queryRef": f"{self.entity}.{self.prop}", "nativeQueryRef": self.prop}


def M(prop: str, entity: str = F) -> Field:
    return Field(entity, prop, "measure")


def C(entity: str, prop: str) -> Field:
    return Field(entity, prop, "column")


@dataclass
class Visual:
    key: str
    visual_type: str
    x: int
    y: int
    w: int
    h: int
    roles: dict[str, list[Field]] = field(default_factory=dict)
    title: str | None = None
    sort: tuple[Field, str] | None = None
    objects: dict[str, Any] | None = None


def visual_json(page: str, v: Visual, z: int) -> dict[str, Any]:
    body: dict[str, Any] = {"visualType": v.visual_type}
    if v.roles:
        query: dict[str, Any] = {
            "queryState": {role: {"projections": [f.projection() for f in fs]} for role, fs in v.roles.items()}
        }
        if v.sort:
            query["sortDefinition"] = {
                "sort": [{"field": v.sort[0].expr, "direction": v.sort[1]}],
                "isDefaultSort": False,
            }
        body["query"] = query
    if v.objects:
        body["objects"] = v.objects
    if v.title:
        body["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{v.title}'")}}]}
    body["drillFilterOtherVisuals"] = True
    return {
        "$schema": SCHEMA["visual"],
        "name": vid(page, v.key),
        "position": {"x": v.x, "y": v.y, "z": z * 1000, "height": v.h, "width": v.w, "tabOrder": z * 1000},
        "visual": body,
    }


def slicer(key: str, f: Field, x: int, y: int, w: int, h: int, mode: str, title: str) -> Visual:
    return Visual(
        key,
        "slicer",
        x,
        y,
        w,
        h,
        {"Values": [f]},
        title,
        objects={"data": [{"properties": {"mode": lit(f"'{mode}'")}}]},
    )


def common_slicers(page: str) -> list[Visual]:
    return [
        slicer(f"{page}-dir", C("DimDirection", "direction"), 16, 16, 220, 64, "Dropdown", "Direction"),
        slicer(f"{page}-date", C("DimDate", "date"), 252, 16, 420, 64, "Between", "Date range"),
        slicer(f"{page}-state", C("DimAirport", "state"), 688, 16, 180, 64, "Dropdown", "State"),
    ]


def kpi(key: str, prop: str, x: int, title: str) -> Visual:
    return Visual(key, "card", x, 96, 236, 104, {"Values": [M(prop)]}, title)


PAGES: list[tuple[str, str, list[Visual]]] = [
    (
        "executive",
        "Executive Performance Overview",
        [
            *common_slicers("exec"),
            Visual("exec-through", "card", 1064, 16, 200, 64, {"Values": [M("Data Through")]}, "Data through"),
            kpi("exec-flights", "Total Flights", 16, "Flights"),
            kpi("exec-ontime", "On-Time %", 268, "On-time rate"),
            kpi("exec-yoy", "On-Time % YoY Change (pts)", 520, "On-time vs prior year"),
            kpi("exec-cancel", "Cancellation Rate", 772, "Cancellation rate"),
            Visual(
                "exec-delay", "card", 1024, 96, 240, 104, {"Values": [M("Average Delay (min)")]}, "Average delay (min)"
            ),
            Visual(
                "exec-trend",
                "lineChart",
                16,
                216,
                760,
                488,
                {"Category": [C("DimDate", "month_start")], "Y": [M("On-Time %"), M("Network On-Time %")]},
                "On-time rate by month (selection vs all monitored airports)",
            ),
            Visual(
                "exec-rank",
                "clusteredBarChart",
                792,
                216,
                472,
                488,
                {"Category": [C("DimAirport", "iata_code")], "Y": [M("On-Time %")]},
                "Airports ranked by on-time rate",
                sort=(M("On-Time %"), "Descending"),
            ),
        ],
    ),
    (
        "comparison",
        "Airport Comparison",
        [
            *common_slicers("cmp"),
            Visual(
                "cmp-matrix",
                "tableEx",
                16,
                96,
                620,
                608,
                {
                    "Values": [
                        C("DimAirport", "iata_code"),
                        C("DimAirport", "city"),
                        M("Total Flights"),
                        M("On-Time %"),
                        M("Cancellation Rate"),
                        M("Average Delay (min)"),
                        M("Rank by Average Delay"),
                    ]
                },
                "Airport scorecard (rank 1 = worst average delay)",
                sort=(M("On-Time %"), "Descending"),
            ),
            Visual(
                "cmp-heatmap",
                "pivotTable",
                652,
                96,
                612,
                384,
                {
                    "Rows": [C("DimAirport", "iata_code")],
                    "Columns": [C("DimDate", "year_month")],
                    "Values": [M("On-Time %")],
                },
                "On-time % by airport and month",
            ),
            Visual(
                "cmp-dist",
                "clusteredColumnChart",
                652,
                496,
                612,
                208,
                {
                    "Y": [
                        M("Flights Early"),
                        M("Flights 0-14 min late"),
                        M("Flights 15-29 min late"),
                        M("Flights 30-59 min late"),
                        M("Flights 60-119 min late"),
                        M("Flights 120+ min late"),
                    ]
                },
                "Delay distribution (operated, non-diverted flights)",
            ),
        ],
    ),
    (
        "drivers",
        "Delay Drivers",
        [
            *common_slicers("drv"),
            Visual(
                "drv-wx",
                "card",
                16,
                96,
                300,
                104,
                {"Values": [M("Weather Share of Delay Minutes")]},
                "Extreme-weather share of cause minutes",
            ),
            Visual(
                "drv-nas",
                "card",
                332,
                96,
                300,
                104,
                {"Values": [M("NAS Share of Delay Minutes")]},
                "NAS share of cause minutes",
            ),
            Visual(
                "drv-total",
                "card",
                648,
                96,
                300,
                104,
                {"Values": [M("Total Cause Minutes")]},
                "Attributed delay minutes",
            ),
            Visual(
                "drv-mix",
                "hundredPercentStackedBarChart",
                16,
                216,
                760,
                488,
                {
                    "Category": [C("DimAirport", "iata_code")],
                    "Y": [
                        M("Cause Minutes - Late Aircraft"),
                        M("Cause Minutes - Carrier"),
                        M("Cause Minutes - NAS"),
                        M("Cause Minutes - Weather"),
                        M("Cause Minutes - Security"),
                    ],
                },
                "Reported delay-cause mix by airport (attribution, not proven causation)",
                sort=(M("Total Cause Minutes"), "Descending"),
            ),
            Visual(
                "drv-cancel",
                "donutChart",
                792,
                216,
                472,
                236,
                {
                    "Y": [
                        M("Cancellations - Carrier"),
                        M("Cancellations - Weather"),
                        M("Cancellations - NAS"),
                        M("Cancellations - Security"),
                    ]
                },
                "Cancellations by reported cause",
            ),
            Visual(
                "drv-trend",
                "lineChart",
                792,
                468,
                472,
                236,
                {
                    "Category": [C("DimDate", "month_start")],
                    "Y": [M("Cause Minutes - Weather"), M("Cause Minutes - NAS")],
                },
                "Weather and NAS delay minutes by month",
            ),
        ],
    ),
    (
        "temporal",
        "Seasonal and Temporal Insights",
        [
            *common_slicers("tmp"),
            Visual(
                "tmp-month",
                "clusteredColumnChart",
                16,
                96,
                620,
                296,
                {"Category": [C("DimDate", "month_short")], "Series": [C("DimDate", "year")], "Y": [M("On-Time %")]},
                "On-time % by calendar month and year",
            ),
            Visual(
                "tmp-dow",
                "clusteredColumnChart",
                652,
                96,
                612,
                296,
                {"Category": [C("DimDate", "day_short")], "Y": [M("On-Time %")]},
                "On-time % by day of week",
            ),
            Visual(
                "tmp-hour",
                "lineChart",
                16,
                408,
                620,
                296,
                {"Category": [C("FactAirportHourly", "hour_local")], "Y": [M("Hourly On-Time %", "FactAirportHourly")]},
                "On-time % by scheduled local hour",
            ),
            Visual(
                "tmp-carrier",
                "clusteredBarChart",
                652,
                408,
                612,
                296,
                {"Category": [C("DimCarrier", "carrier_name")], "Y": [M("Carrier On-Time %", "FactCarrierMonthly")]},
                "On-time % by reporting carrier",
                sort=(M("Carrier On-Time %", "FactCarrierMonthly"), "Descending"),
            ),
        ],
    ),
]


def direction_filter() -> dict[str, Any]:
    """Report-level default: arrivals (DOT on-time convention). Users can change it."""
    return {
        "filters": [
            {
                "name": vid("filter", "direction"),
                "field": column("DimDirection", "direction"),
                "type": "Categorical",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "d", "Entity": "DimDirection", "Type": 0}],
                    "Where": [
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [
                                        {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Source": "d"}},
                                                "Property": "direction",
                                            }
                                        }
                                    ],
                                    "Values": [[{"Literal": {"Value": "'arrival'"}}]],
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }


def dump(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_report(rp: Path) -> tuple[int, int]:
    dump(
        rp / "definition.pbir",
        {
            "$schema": SCHEMA["pbir"],
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../AeroPulse.SemanticModel"}},
        },
    )
    d = rp / "definition"
    dump(d / "version.json", {"$schema": SCHEMA["version"], "version": "2.0.0"})
    dump(
        d / "report.json",
        {
            "$schema": SCHEMA["report"],
            "themeCollection": {
                "customTheme": {"name": THEME_FILE, "reportVersionAtImport": VERSIONS, "type": "RegisteredResources"}
            },
            "filterConfig": direction_filter(),
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}],
                }
            ],
            "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True},
        },
    )
    dump(rp / "StaticResources" / "RegisteredResources" / THEME_FILE, THEME)
    order, count = [], 0
    for key, title, visuals in PAGES:
        name = vid("page", key)
        order.append(name)
        dump(
            d / "pages" / name / "page.json",
            {
                "$schema": SCHEMA["page"],
                "name": name,
                "displayName": title,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
        )
        for z, v in enumerate(visuals):
            vj = visual_json(name, v, z)
            dump(d / "pages" / name / "visuals" / vj["name"] / "visual.json", vj)
            count += 1
    dump(d / "pages" / "pages.json", {"$schema": SCHEMA["pages"], "pageOrder": order, "activePageName": order[0]})
    return len(PAGES), count
