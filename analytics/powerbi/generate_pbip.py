"""Generate the AeroPulse Power BI Project (PBIP) from one declarative spec.

Outputs (text, diff-friendly, documented Microsoft formats):

* ``AeroPulse.SemanticModel/`` — TMDL semantic model: star schema over the Parquet files in
  ``analytics/powerbi/data`` (Power Query ``Parquet.Document``), relationships, a marked
  date table, and all DAX measures.
* ``AeroPulse.Report/`` — a report shell bound to the model, with the four required pages
  created (empty canvases). Visuals are specified in docs/dashboards/powerbi-report.md and are
  placed in Power BI Desktop.
* ``AeroPulse.pbip`` — the project entry point.
* ``analytics/dax/measures.dax`` — the same measures as a reviewable DAX script.

Column metadata is read from the exported Parquet files, so the model always matches the
data. Run after the BTS pipeline export:

    uv run --project services/api --group pipeline python analytics/powerbi/generate_pbip.py

NOTE: generated on macOS; Power BI Desktop (Windows) is required to open and validate it.
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
NS = uuid.UUID("6f1c1d5e-2b8a-4a5e-9d55-aeb0a1c0ffee")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


DUCK_TO_TMDL = {
    "VARCHAR": ("string", "none"),
    "DATE": ("dateTime", "none"),
    "TIMESTAMP": ("dateTime", "none"),
    "TIMESTAMP WITH TIME ZONE": ("dateTime", "none"),
    "BIGINT": ("int64", "sum"),
    "INTEGER": ("int64", "sum"),
    "SMALLINT": ("int64", "sum"),
    "DOUBLE": ("double", "sum"),
    "BOOLEAN": ("boolean", "none"),
}
M_TYPES = {
    "string": "type text",
    "dateTime": "type date",
    "int64": "Int64.Type",
    "double": "type number",
    "boolean": "type logical",
}
SORT_BY = {
    ("DimDate", "month_short"): "month",
    ("DimDate", "day_short"): "iso_day_of_week",
    ("DimDate", "season"): "month",
}
KEY_LIKE = {"hour_local", "year", "quarter", "month", "iso_day_of_week", "latitude", "longitude"}


@dataclass
class Measure:
    name: str
    expr: str
    fmt: str
    folder: str
    description: str


@dataclass
class Table:
    name: str
    file: str
    hidden_cols: set[str] = field(default_factory=set)
    measures: list[Measure] = field(default_factory=list)
    is_date: bool = False


F = "FactAirportDaily"
ARR = f'{F}[direction] = "arrival"'
DEP = f'{F}[direction] = "departure"'

MEASURES = [
    # Volume
    Measure(
        "Total Flights",
        f"SUM({F}[flights])",
        "#,0",
        "Volume",
        "Scheduled flight legs at the selected airports (each flight counts once per direction selected).",
    ),
    Measure("Arrival Flights", f"CALCULATE([Total Flights], {ARR})", "#,0", "Volume", "Scheduled arrivals."),
    Measure("Departure Flights", f"CALCULATE([Total Flights], {DEP})", "#,0", "Volume", "Scheduled departures."),
    Measure("Cancelled Flights", f"SUM({F}[cancelled])", "#,0", "Volume", "BTS-reported cancellations."),
    Measure("Diverted Flights", f"SUM({F}[diverted])", "#,0", "Volume", "BTS-reported diversions."),
    Measure(
        "Delayed Flights",
        f"SUM({F}[delayed_15])",
        "#,0",
        "Volume",
        "Operated, non-diverted flights 15+ minutes late (DOT definition).",
    ),
    # Rates
    Measure(
        "On-Time %",
        f"DIVIDE(SUM({F}[ontime_num]), SUM({F}[ontime_den]))",
        "0.0%",
        "Rates",
        "On-time (< 15 min late) / operated non-diverted flights with a reported delay. Cancelled and diverted excluded.",
    ),
    Measure("Arrival On-Time %", f"CALCULATE([On-Time %], {ARR})", "0.0%", "Rates", "DOT arrival on-time rate."),
    Measure("Departure On-Time %", f"CALCULATE([On-Time %], {DEP})", "0.0%", "Rates", "Departure on-time rate."),
    Measure(
        "Cancellation Rate", "DIVIDE([Cancelled Flights], [Total Flights])", "0.00%", "Rates", "Cancelled / scheduled."
    ),
    Measure("Diversion Rate", "DIVIDE([Diverted Flights], [Total Flights])", "0.00%", "Rates", "Diverted / scheduled."),
    # Delay minutes
    Measure(
        "Average Delay (min)",
        f"DIVIDE(SUM({F}[delay_sum_min]), SUM({F}[ontime_den]))",
        "0.0",
        "Delay",
        "Mean delay in minutes; early flights count as negative.",
    ),
    Measure(
        "Average Arrival Delay (min)",
        f"CALCULATE([Average Delay (min)], {ARR})",
        "0.0",
        "Delay",
        "Mean arrival delay (ArrDelay).",
    ),
    Measure(
        "Average Departure Delay (min)",
        f"CALCULATE([Average Delay (min)], {DEP})",
        "0.0",
        "Delay",
        "Mean departure delay (DepDelay).",
    ),
    # Causes (carrier-reported attribution, not proven causation)
    Measure(
        "Cause Minutes - Carrier", f"SUM({F}[carrier_delay_min])", "#,0", "Delay causes", "Air-carrier delay minutes."
    ),
    Measure(
        "Cause Minutes - Weather",
        f"SUM({F}[weather_delay_min])",
        "#,0",
        "Delay causes",
        "Extreme-weather delay minutes.",
    ),
    Measure(
        "Cause Minutes - NAS",
        f"SUM({F}[nas_delay_min])",
        "#,0",
        "Delay causes",
        "National Airspace System delay minutes.",
    ),
    Measure(
        "Cause Minutes - Security", f"SUM({F}[security_delay_min])", "#,0", "Delay causes", "Security delay minutes."
    ),
    Measure(
        "Cause Minutes - Late Aircraft",
        f"SUM({F}[late_aircraft_delay_min])",
        "#,0",
        "Delay causes",
        "Late-arriving aircraft delay minutes.",
    ),
    Measure(
        "Total Cause Minutes",
        "[Cause Minutes - Carrier] + [Cause Minutes - Weather] + [Cause Minutes - NAS] + "
        "[Cause Minutes - Security] + [Cause Minutes - Late Aircraft]",
        "#,0",
        "Delay causes",
        "Sum of attributed delay minutes.",
    ),
    Measure(
        "Weather Share of Delay Minutes",
        "DIVIDE([Cause Minutes - Weather], [Total Cause Minutes])",
        "0.0%",
        "Delay causes",
        "Share of attributed minutes coded as extreme weather.",
    ),
    Measure(
        "NAS Share of Delay Minutes",
        "DIVIDE([Cause Minutes - NAS], [Total Cause Minutes])",
        "0.0%",
        "Delay causes",
        "Share coded as NAS (includes non-extreme weather handled by ATC).",
    ),
    # Time intelligence
    Measure(
        "On-Time % (Previous Month)",
        "CALCULATE([On-Time %], DATEADD(DimDate[date], -1, MONTH))",
        "0.0%",
        "Time intelligence",
        "On-time rate for the prior month of the current filter context.",
    ),
    Measure(
        "On-Time % MoM Change (pts)",
        "VAR cur = [On-Time %] VAR prev = [On-Time % (Previous Month)] "
        "RETURN IF(NOT ISBLANK(cur) && NOT ISBLANK(prev), cur - prev)",
        "+0.0%;-0.0%;0.0%",
        "Time intelligence",
        "Percentage-point change vs previous month; blank if not loaded.",
    ),
    Measure(
        "On-Time % (Previous Year)",
        "CALCULATE([On-Time %], SAMEPERIODLASTYEAR(DimDate[date]))",
        "0.0%",
        "Time intelligence",
        "Same period one year earlier.",
    ),
    Measure(
        "On-Time % YoY Change (pts)",
        "VAR cur = [On-Time %] VAR prev = [On-Time % (Previous Year)] "
        "RETURN IF(NOT ISBLANK(cur) && NOT ISBLANK(prev), cur - prev)",
        "+0.0%;-0.0%;0.0%",
        "Time intelligence",
        "Percentage-point change vs same period last year; blank if not loaded.",
    ),
    Measure(
        "Flights YoY Change %",
        "VAR prev = CALCULATE([Total Flights], SAMEPERIODLASTYEAR(DimDate[date])) "
        "RETURN IF(NOT ISBLANK(prev), DIVIDE([Total Flights] - prev, prev))",
        "+0.0%;-0.0%;0.0%",
        "Time intelligence",
        "Volume growth vs same period last year.",
    ),
    # Ranking / comparison
    Measure(
        "Rank by Average Delay",
        "IF(HASONEVALUE(DimAirport[iata_code]), "
        "RANKX(ALLSELECTED(DimAirport[iata_code]), [Average Delay (min)], , DESC, DENSE))",
        "0",
        "Ranking",
        "1 = worst average delay among selected airports.",
    ),
    Measure(
        "Rank by On-Time %",
        "IF(HASONEVALUE(DimAirport[iata_code]), RANKX(ALLSELECTED(DimAirport[iata_code]), [On-Time %], , DESC, DENSE))",
        "0",
        "Ranking",
        "1 = best on-time rate among selected airports.",
    ),
    Measure(
        "Network On-Time %",
        "CALCULATE([On-Time %], ALL(DimAirport))",
        "0.0%",
        "Ranking",
        "All monitored airports, same period and direction.",
    ),
    Measure(
        "Selected Airport vs Network (pts)",
        "IF(HASONEVALUE(DimAirport[iata_code]), [On-Time %] - [Network On-Time %])",
        "+0.0%;-0.0%;0.0%",
        "Ranking",
        "Selected airport's on-time rate minus the network rate.",
    ),
    Measure(
        "Data Through",
        'FORMAT(MAX(DimDate[date]), "mmm yyyy")',
        "",
        "Metadata",
        "Latest loaded BTS month (BTS publishes with a ~2-3 month lag).",
    ),
]


MEASURES += [
    Measure(f"Flights {label}", f"SUM({F}[{col}])", "#,0", "Distribution", f"Operated, non-diverted flights {desc}.")
    for label, col, desc in (
        ("Early", "bucket_early", "arriving/departing early"),
        ("0-14 min late", "bucket_0_14", "0-14 minutes late (on time)"),
        ("15-29 min late", "bucket_15_29", "15-29 minutes late"),
        ("30-59 min late", "bucket_30_59", "30-59 minutes late"),
        ("60-119 min late", "bucket_60_119", "60-119 minutes late"),
        ("120+ min late", "bucket_120_plus", "120 or more minutes late"),
    )
] + [
    Measure(
        f"Cancellations - {label}", f"SUM({F}[{col}])", "#,0", "Cancellation causes", f"Cancellations coded {code}."
    )
    for label, col, code in (
        ("Carrier", "cancel_carrier", "A (carrier)"),
        ("Weather", "cancel_weather", "B (weather)"),
        ("NAS", "cancel_nas", "C (National Airspace System)"),
        ("Security", "cancel_security", "D (security)"),
    )
]

HOURLY_MEASURES = [
    Measure("Hourly Flights", "SUM(FactAirportHourly[flights])", "#,0", "Hourly", "Flights by scheduled local hour."),
    Measure(
        "Hourly On-Time %",
        "DIVIDE(SUM(FactAirportHourly[ontime_num]), SUM(FactAirportHourly[ontime_den]))",
        "0.0%",
        "Hourly",
        "On-time rate by scheduled local hour.",
    ),
]
CARRIER_MEASURES = [
    Measure("Carrier Flights", "SUM(FactCarrierMonthly[flights])", "#,0", "Carrier", "Flights by reporting carrier."),
    Measure(
        "Carrier On-Time %",
        "DIVIDE(SUM(FactCarrierMonthly[ontime_num]), SUM(FactCarrierMonthly[ontime_den]))",
        "0.0%",
        "Carrier",
        "On-time rate by reporting carrier.",
    ),
]

TABLES = [
    Table("DimDate", "dim_date.parquet", is_date=True),
    Table("DimAirport", "dim_airport.parquet"),
    Table("DimCarrier", "dim_carrier.parquet"),
    Table(F, "fact_airport_daily.parquet", hidden_cols={"airport_iata", "flight_date"}, measures=MEASURES),
    Table(
        "FactAirportHourly",
        "fact_airport_hourly.parquet",
        hidden_cols={"airport_iata", "year_month"},
        measures=HOURLY_MEASURES,
    ),
    Table(
        "FactCarrierMonthly",
        "fact_carrier_monthly.parquet",
        hidden_cols={"airport_iata", "year_month", "carrier_code"},
        measures=CARRIER_MEASURES,
    ),
]

RELATIONSHIPS = [
    (F, "flight_date", "DimDate", "date"),
    (F, "airport_iata", "DimAirport", "iata_code"),
    ("FactAirportHourly", "year_month", "DimDate", "date"),
    ("FactAirportHourly", "airport_iata", "DimAirport", "iata_code"),
    ("FactCarrierMonthly", "year_month", "DimDate", "date"),
    ("FactCarrierMonthly", "airport_iata", "DimAirport", "iata_code"),
    ("FactCarrierMonthly", "carrier_code", "DimCarrier", "carrier_code"),
    (F, "direction", "DimDirection", "direction"),
    ("FactAirportHourly", "direction", "DimDirection", "direction"),
    ("FactCarrierMonthly", "direction", "DimDirection", "direction"),
]

# Public, anonymous source for the exported star schema (U.S. public-domain BTS data), so the
# model refreshes in the Power BI service without a gateway. Forks can change the parameter.
DATA_URL = (
    "https://raw.githubusercontent.com/Gnanasudharsan/aeropulse-aviation-intelligence/main/analytics/powerbi/data/"
)

DIM_DIRECTION_TMDL = f"""table DimDirection
\tlineageTag: {tag("table", "DimDirection")}

\t/// arrival = flights arriving at the airport (DOT on-time convention); departure = flights departing it.
\tcolumn direction
\t\tdataType: string
\t\tisNameInferred
\t\tlineageTag: {tag("column", "DimDirection", "direction")}
\t\tsummarizeBy: none
\t\tsourceColumn: [direction]

\tpartition DimDirection = calculated
\t\tmode: import
\t\tsource = DATATABLE("direction", STRING, {{{{"arrival"}}, {{"departure"}}}})
"""

PAGES = ["Executive Performance Overview", "Airport Comparison", "Delay Drivers", "Seasonal and Temporal Insights"]


def schema(file: str) -> list[tuple[str, str]]:
    con = duckdb.connect()
    rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{DATA / file}')").fetchall()
    return [(r[0], r[1]) for r in rows]


def esc(name: str) -> str:
    return f"'{name}'" if any(c in name for c in " -%()&") else name


def table_tmdl(t: Table) -> str:
    cols = schema(t.file)
    lines = [f"table {t.name}", f"\tlineageTag: {tag('table', t.name)}"]
    if t.is_date:
        lines.append("\tdataCategory: Time")
    lines.append("")
    for m in t.measures:
        expr = m.expr if "\n" not in m.expr else "\n\t\t\t" + m.expr.replace("\n", "\n\t\t\t")
        lines += [f"\t/// {m.description}", f"\tmeasure {esc(m.name)} = {expr}"]
        if m.fmt:
            lines.append(f"\t\tformatString: {m.fmt}")
        lines += [f"\t\tdisplayFolder: {m.folder}", f"\t\tlineageTag: {tag('measure', t.name, m.name)}", ""]
    m_types = []
    for col, dtype in cols:
        tm_type, summarize = DUCK_TO_TMDL.get(dtype, ("string", "none"))
        if col in KEY_LIKE or col.endswith(("_code", "_iata")):
            summarize = "none"
        lines += [f"\tcolumn {esc(col)}", f"\t\tdataType: {tm_type}"]
        if t.is_date and col == "date":
            lines.append("\t\tisKey")
        if tm_type == "dateTime":
            lines.append("\t\tformatString: yyyy-mm-dd")
        if (t.name, col) in SORT_BY:
            lines.append(f"\t\tsortByColumn: {SORT_BY[(t.name, col)]}")
        if col in t.hidden_cols or (t.measures and summarize == "sum"):
            lines.append("\t\tisHidden")
        lines += [
            f"\t\tlineageTag: {tag('column', t.name, col)}",
            f"\t\tsummarizeBy: {summarize}",
            f"\t\tsourceColumn: {col}",
            "",
        ]
        m_types.append(f'{{"{col}", {M_TYPES[tm_type]}}}')
    m = (
        "let\n"
        f'\t\t\t\t    Source = Parquet.Document(Binary.Buffer(Web.Contents(DataUrl, [RelativePath = "{t.file}"]))),\n'
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Source, {{{', '.join(m_types)}}})\n"
        "\t\t\t\tin\n\t\t\t\t    Typed"
    )
    lines += [f"\tpartition {t.name} = m", "\t\tmode: import", "\t\tsource =", f"\t\t\t\t{m}", ""]
    return "\n".join(lines)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    sm = ROOT / "AeroPulse.SemanticModel"
    rp = ROOT / "AeroPulse.Report"
    for d in (sm, rp):
        shutil.rmtree(d, ignore_errors=True)

    write(
        ROOT / "AeroPulse.pbip",
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                "version": "1.0",
                "artifacts": [{"report": {"path": "AeroPulse.Report"}}],
                "settings": {"enableAutoRecovery": True},
            },
            indent=2,
        ),
    )
    write(sm / "definition.pbism", json.dumps({"version": "4.0", "settings": {}}, indent=2))
    write(sm / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    write(
        sm / "definition" / "model.tmdl",
        "\n".join(
            [
                "model Model",
                "\tculture: en-US",
                "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
                "\tdiscourageImplicitMeasures",
                "\tsourceQueryCulture: en-US",
                "",
            ]
            + [f"ref table {t.name}" for t in TABLES]
            + ["ref table DimDirection"]
        ),
    )
    write(
        sm / "definition" / "expressions.tmdl",
        "\n".join(
            [
                "/// Base URL of the exported Parquet star schema (public GitHub raw files; must end with /).",
                f'expression DataUrl = "{DATA_URL}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                f"\tlineageTag: {tag('expression', 'DataUrl')}",
                "",
                "\tannotation PBI_ResultType = Text",
            ]
        ),
    )
    for t in TABLES:
        write(sm / "definition" / "tables" / f"{t.name}.tmdl", table_tmdl(t))
    write(sm / "definition" / "tables" / "DimDirection.tmdl", DIM_DIRECTION_TMDL)
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [f"relationship {tag('rel', ft, fc, tt)}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    write(sm / "definition" / "relationships.tmdl", "\n".join(rel))

    from generate_report import write_report  # local module

    pages, visuals = write_report(rp)

    dax = ["// AeroPulse DAX measures (generated by analytics/powerbi/generate_pbip.py — do not edit by hand)", ""]
    for t in TABLES:
        for m in t.measures:
            dax += [f"// {m.folder} · {m.description}", f"[{m.name}] =", f"    {m.expr}", ""]
    write(ROOT.parent / "dax" / "measures.dax", "\n".join(dax))
    n = sum(len(t.measures) for t in TABLES)
    print(
        f"PBIP written: {len(TABLES) + 1} tables, {len(RELATIONSHIPS)} relationships, {n} measures, "
        f"{pages} pages, {visuals} visuals"
    )


if __name__ == "__main__":
    main()
