from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_bi_views_sql_matches_migration() -> None:
    spec = importlib.util.spec_from_file_location(
        "m0004", ROOT / "services/api/migrations/versions/0004_bi_views.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql_file = (ROOT / "analytics/sql/bi_views.sql").read_text()
    assert module.BI_VIEWS_SQL.strip() == sql_file.strip()
