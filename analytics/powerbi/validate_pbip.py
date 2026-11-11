"""Validate the generated Power BI Project without Power BI Desktop.

Checks (each one fails the run):

1. Every report file validates against the official Microsoft JSON schema it declares
   (github.com/microsoft/json-schemas, fabric/item/report), and the custom theme validates
   against Microsoft's report-theme schema (github.com/microsoft/powerbi-desktop-samples).
2. Model integrity (parsed from TMDL): every field used by a visual or filter exists with the
   right kind (column vs measure); every `[Measure]` and `Table[Column]` referenced in DAX
   exists; relationship and sortByColumn targets exist; every relationship joins columns of
   the same data type.
3. Data sources: every Parquet file the model reads is reachable at its URL, and its columns
   match the TMDL columns.

Not covered (needs Microsoft's Analysis Services engine / Power BI Desktop): DAX evaluation
and TMDL parsing by Microsoft's own serializer.

    uv run --project services/api --group pipeline python analytics/powerbi/validate_pbip.py \
        --schemas <path to microsoft/json-schemas checkout> --theme-schema <reportThemeSchema-*.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

import duckdb
from jsonschema import Draft7Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
SM = ROOT / "AeroPulse.SemanticModel" / "definition"
RP = ROOT / "AeroPulse.Report"
PREFIX = "https://developer.microsoft.com/json-schemas/"


# --------------------------------------------------------------------------- 1. JSON schemas


def schema_registry(schemas_root: Path) -> Registry:
    def retrieve(uri: str) -> Resource:
        if not uri.startswith(PREFIX):
            raise LookupError(uri)
        path = schemas_root / uri.removeprefix(PREFIX)
        return Resource.from_contents(json.loads(path.read_text()))

    return Registry(retrieve=retrieve)  # type: ignore[call-arg]


def validate_json(schemas_root: Path, theme_schema: Path) -> list[str]:
    registry = schema_registry(schemas_root)
    errors: list[str] = []
    files = [*sorted(RP.rglob("*.json")), RP / "definition.pbir"]
    for f in files:
        data = json.loads(f.read_text())
        uri = data.get("$schema")
        if f.parent.name == "RegisteredResources":
            schema = json.loads(theme_schema.read_text())
            validator = Draft7Validator(schema)
        elif not uri:
            errors.append(f"{f.relative_to(ROOT)}: missing $schema")
            continue
        else:
            schema = registry.get_or_retrieve(uri).value.contents
            validator = Draft7Validator(schema, registry=registry)
        for e in validator.iter_errors(data):
            errors.append(f"{f.relative_to(ROOT)}: {'/'.join(map(str, e.absolute_path))}: {e.message[:200]}")
    print(f"[schemas] {len(files)} report files checked against Microsoft schemas")
    return errors


# --------------------------------------------------------------------------- 2. model integrity

TABLE_RE = re.compile(r"^table (.+)$")
COL_RE = re.compile(r"^\tcolumn (.+)$")
MEAS_RE = re.compile(r"^\tmeasure (.+?) = (.+)$")
TYPE_RE = re.compile(r"^\t\tdataType: (\w+)$")
SORT_RE = re.compile(r"^\t\tsortByColumn: (.+)$")


def unquote(name: str) -> str:
    name = name.strip()
    return name[1:-1] if name.startswith("'") and name.endswith("'") else name


def parse_model() -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str], list[tuple[str, str, str]]]:
    columns: dict[str, dict[str, str]] = {}
    measures: dict[str, str] = {}  # name -> table
    dax: dict[str, str] = {}
    sorts: list[tuple[str, str, str]] = []
    for f in sorted((SM / "tables").glob("*.tmdl")):
        table, current = None, None
        for line in f.read_text().splitlines():
            if m := TABLE_RE.match(line):
                table = unquote(m.group(1))
                columns[table] = {}
            elif m := COL_RE.match(line):
                current = unquote(m.group(1))
                columns[table][current] = "?"
            elif m := MEAS_RE.match(line):
                name = unquote(m.group(1))
                measures[name] = table
                dax[name] = m.group(2)
                current = None
            elif (m := TYPE_RE.match(line)) and current:
                columns[table][current] = m.group(1)
            elif (m := SORT_RE.match(line)) and current:
                sorts.append((table, current, unquote(m.group(1))))
    return columns, measures, dax, sorts


def walk_fields(node: Any, out: list[tuple[str, str, str]]) -> None:
    if isinstance(node, dict):
        for kind in ("Measure", "Column"):
            if kind in node and isinstance(node[kind], dict):
                src = node[kind]["Expression"].get("SourceRef", {})
                if "Entity" in src:
                    out.append((kind, src["Entity"], node[kind]["Property"]))
        for v in node.values():
            walk_fields(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_fields(v, out)


DAX_MEASURE = re.compile(r"(?<![\w'\]])\[([^\]]+)\]")
DAX_COLUMN = re.compile(r"(?:'([^']+)'|\b([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]")


def validate_model() -> list[str]:
    columns, measures, dax, sorts = parse_model()
    errors: list[str] = []
    # Visual / filter fields
    fields: list[tuple[str, str, str]] = []
    for f in RP.rglob("*.json"):
        walk_fields(json.loads(f.read_text()), fields)
    for kind, table, prop in fields:
        if table not in columns:
            errors.append(f"report references unknown table {table}")
        elif kind == "Column" and prop not in columns[table]:
            errors.append(f"report references unknown column {table}[{prop}]")
        elif kind == "Measure" and measures.get(prop) != table:
            errors.append(f"report references unknown measure {table}[{prop}]")
    # DAX references
    for name, expr in dax.items():
        for t1, t2, col in DAX_COLUMN.findall(expr):
            table = t1 or t2
            if table not in columns or col not in columns[table]:
                errors.append(f"measure [{name}] references unknown column {table}[{col}]")
        stripped = DAX_COLUMN.sub("", expr)
        for ref in DAX_MEASURE.findall(stripped):
            if ref not in measures:
                errors.append(f"measure [{name}] references unknown measure [{ref}]")
    # Relationships
    rel = (SM / "relationships.tmdl").read_text()
    pairs = re.findall(r"fromColumn: (\w+)\.(\w+)\n\ttoColumn: (\w+)\.(\w+)", rel)
    for ft, fc, tt, tc in pairs:
        for t, c in ((ft, fc), (tt, tc)):
            if c not in columns.get(t, {}):
                errors.append(f"relationship column {t}.{c} does not exist")
        if columns.get(ft, {}).get(fc) != columns.get(tt, {}).get(tc):
            errors.append(f"relationship {ft}.{fc} -> {tt}.{tc} joins different data types")
    for table, col, target in sorts:
        if target not in columns[table]:
            errors.append(f"{table}[{col}] sortByColumn target {target} missing")
    print(
        f"[model] {len(columns)} tables, {sum(len(c) for c in columns.values())} columns, {len(measures)} measures, "
        f"{len(pairs)} relationships, {len(fields)} report field references checked"
    )
    return errors


# --------------------------------------------------------------------------- 3. data sources


def validate_sources() -> list[str]:
    errors: list[str] = []
    base = re.search(r'expression DataUrl = "([^"]+)"', (SM / "expressions.tmdl").read_text())
    if not base:
        return ["DataUrl parameter not found"]
    con = duckdb.connect()
    checked = 0
    for f in sorted((SM / "tables").glob("*.tmdl")):
        text = f.read_text()
        m = re.search(r'RelativePath = "([^"]+)"', text)
        if not m:
            continue  # calculated table
        url = base.group(1) + m.group(1)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AeroPulse-validate"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = resp.read()
        except Exception as exc:
            errors.append(f"{url}: not reachable ({exc})")
            continue
        tmp = ROOT / f".validate-{m.group(1)}"
        tmp.write_bytes(payload)
        remote_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{tmp}')").fetchall()]
        tmp.unlink()
        tmdl_cols = [unquote(c) for c in re.findall(r"^\tcolumn (.+)$", text, re.M)]
        if remote_cols != tmdl_cols:
            errors.append(f"{m.group(1)}: remote columns {remote_cols} != TMDL columns {tmdl_cols}")
        checked += 1
    print(f"[sources] {checked} Parquet files fetched from {base.group(1)} and matched to TMDL")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schemas", type=Path, required=True, help="checkout of github.com/microsoft/json-schemas")
    ap.add_argument("--theme-schema", type=Path, required=True, help="reportThemeSchema-*.json")
    ap.add_argument("--skip-sources", action="store_true", help="skip fetching the Parquet URLs")
    args = ap.parse_args()
    errors = validate_json(args.schemas, args.theme_schema) + validate_model()
    if not args.skip_sources:
        errors += validate_sources()
    for e in errors:
        print("ERROR", e)
    print("VALID" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
