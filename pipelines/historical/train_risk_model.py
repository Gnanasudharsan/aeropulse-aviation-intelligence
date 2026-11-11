"""Train and validate the disruption-risk model (Phase 6).

Question: given the METAR observed *before* a departure hour starts, plus calendar features
and the airport's historical base rate, how likely is that hour to be disrupted?

Label (BTS, per airport x local date x scheduled local departure hour, >= 5 departures):
    disrupted = (departures delayed >= 15 min + cancelled) / scheduled departures >= 0.35

Features (all known before the hour starts — no target leakage):
    METAR at or before hour start (<= 75 min old): visibility/ceiling flags, wind, gust,
    thunderstorm / snow-freezing / rain flags; hour & month (cyclic), weekend;
    airport base rate computed on the TRAINING period only.
FAA advisories are not used: no historical archive is available to us.

Validation: chronological split (last 6 months held out). Models compared:
    baseline   — logistic regression on airport base rate + hour (no weather)
    logistic   — all features (the served model, explainable)
    hgb        — HistGradientBoosting (reference only)
The logistic model is marked servable only if its test ROC AUC beats the baseline by >= 0.02.

    uv run --project services/api --group pipeline python pipelines/historical/train_risk_model.py
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
from pathlib import Path

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[2]
TRAINING = REPO / "data/derived/training"
METARS = REPO / "data/derived/metar_history"
ARTIFACT = REPO / "services/api/app/data/risk_model.json"
REPORT = REPO / "docs/dashboards/risk-model-report.md"
LABEL_THRESHOLD = 0.35
MIN_FLIGHTS = 5
TEST_MONTHS = 6

FEATURES = [
    "low_visibility",
    "very_low_visibility",
    "low_ceiling",
    "wind_kt",
    "gust_kt",
    "thunderstorm",
    "snow_or_freezing",
    "rain",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
    "weekend",
    "airport_baseline",
]
BASELINE_FEATURES = ["airport_baseline", "hour_sin", "hour_cos"]


def airports() -> list[tuple[str, str]]:
    with (REPO / "services/api/app/data/airports.csv").open() as fh:
        return [(r["iata_code"], r["timezone"]) for r in csv.DictReader(fh)]


def build_dataset(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL icu; LOAD icu;")
    con.execute("CREATE TABLE tz(airport VARCHAR, tz VARCHAR)")
    con.executemany("INSERT INTO tz VALUES (?, ?)", airports())
    con.execute(f"CREATE TABLE dep AS SELECT * FROM read_parquet('{TRAINING}/*.parquet')")
    con.execute(f"CREATE TABLE obs AS SELECT * FROM read_parquet('{METARS}/*.parquet') ORDER BY airport, observed_utc")
    # Hour start in UTC (local wall clock interpreted in the airport's IANA zone).
    con.execute(
        """
        CREATE TABLE hours AS
        SELECT d.*, t.tz,
               timezone('UTC', timezone(t.tz, (d.flight_date + d.hour_local * INTERVAL 1 HOUR)::TIMESTAMP))::TIMESTAMP
                   AS hour_start_utc,
               (d.delayed_15 + d.cancelled)::DOUBLE / d.flights AS disrupted_share
        FROM dep d JOIN tz t USING (airport)
        WHERE d.flights >= ?
        """,
        [MIN_FLIGHTS],
    )
    con.execute(
        """
        CREATE TABLE joined AS
        SELECT h.*, o.observed_utc, o.visibility_sm, o.ceiling_ft, o.wind_kt, o.gust_kt, o.wxcodes
        FROM hours h ASOF LEFT JOIN obs o
          ON h.airport = o.airport AND o.observed_utc <= h.hour_start_utc
        """
    )


def to_frame(con: duckdb.DuckDBPyConnection) -> dict[str, np.ndarray]:
    rows = con.execute(
        """
        SELECT airport, flight_date, hour_local, disrupted_share,
               visibility_sm, ceiling_ft, wind_kt, gust_kt, coalesce(wxcodes, '') AS wx,
               date_diff('minute', observed_utc, hour_start_utc) AS age_min
        FROM joined
        WHERE observed_utc IS NOT NULL AND date_diff('minute', observed_utc, hour_start_utc) <= 75
              AND visibility_sm IS NOT NULL
        ORDER BY flight_date, airport, hour_local
        """
    ).fetchall()
    cols = list(zip(*rows, strict=True))
    return {
        "airport": np.array(cols[0]),
        "date": np.array(cols[1]),
        "hour": np.array(cols[2], dtype=float),
        "share": np.array(cols[3], dtype=float),
        "vis": np.array(cols[4], dtype=float),
        "ceiling": np.array([np.nan if c is None else c for c in cols[5]], dtype=float),
        "wind": np.array([0 if v is None else v for v in cols[6]], dtype=float),
        "gust": np.array([0 if v is None else v for v in cols[7]], dtype=float),
        "wx": np.array(cols[8]),
    }


def build_features(f: dict[str, np.ndarray], baseline: dict[str, float]) -> np.ndarray:
    """Must mirror services/api/app/services/risk_model._features."""
    months = np.array([d.month for d in f["date"]], dtype=float)
    weekend = np.array([1.0 if d.isoweekday() >= 6 else 0.0 for d in f["date"]])
    wx = np.char.upper(f["wx"].astype(str))
    cols = {
        "low_visibility": (f["vis"] < 3).astype(float),
        "very_low_visibility": (f["vis"] < 1).astype(float),
        "low_ceiling": np.where(np.isnan(f["ceiling"]), 0.0, (f["ceiling"] < 1000).astype(float)),
        "wind_kt": f["wind"],
        "gust_kt": f["gust"],
        "thunderstorm": np.char.find(wx, "TS") >= 0,
        "snow_or_freezing": (np.char.find(wx, "SN") >= 0) | (np.char.find(wx, "FZ") >= 0),
        "rain": np.char.find(wx, "RA") >= 0,
        "hour_sin": np.sin(2 * math.pi * f["hour"] / 24),
        "hour_cos": np.cos(2 * math.pi * f["hour"] / 24),
        "month_sin": np.sin(2 * math.pi * months / 12),
        "month_cos": np.cos(2 * math.pi * months / 12),
        "weekend": weekend,
        "airport_baseline": np.array([baseline.get(a, np.nan) for a in f["airport"]]),
    }
    return np.column_stack([np.asarray(cols[k], dtype=float) for k in FEATURES])


def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))), 4),
    }


def main() -> None:
    con = duckdb.connect()
    build_dataset(con)
    f = to_frame(con)
    y_all = (f["share"] >= LABEL_THRESHOLD).astype(int)
    months = sorted({(d.year, d.month) for d in f["date"]})
    if len(months) < TEST_MONTHS + 6:
        raise SystemExit(f"need >= {TEST_MONTHS + 6} months of joined data, have {len(months)}")
    cutoff = dt.date(*months[-TEST_MONTHS], 1)
    train = np.array([d < cutoff for d in f["date"]])
    test = ~train

    # Airport base rate from the TRAINING period only (prevents leakage into the test set).
    baseline = {a: float(y_all[train & (f["airport"] == a)].mean()) for a in np.unique(f["airport"][train])}
    X = build_features(f, baseline)
    ok = ~np.isnan(X).any(axis=1)
    X, y, tr, te = X[ok], y_all[ok], train[ok], test[ok]

    scaler = StandardScaler().fit(X[tr])
    Xs = scaler.transform(X)
    idx_base = [FEATURES.index(c) for c in BASELINE_FEATURES]

    base = LogisticRegression(max_iter=1000).fit(Xs[tr][:, idx_base], y[tr])
    logit = LogisticRegression(max_iter=2000, C=1.0).fit(Xs[tr], y[tr])
    hgb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=7).fit(X[tr], y[tr])

    results = {
        "baseline": metrics(y[te], base.predict_proba(Xs[te][:, idx_base])[:, 1]),
        "logistic": metrics(y[te], logit.predict_proba(Xs[te])[:, 1]),
        "hgb": metrics(y[te], hgb.predict_proba(X[te])[:, 1]),
    }
    beats = results["logistic"]["roc_auc"] >= results["baseline"]["roc_auc"] + 0.02
    first, last = dt.date(*months[0], 1), dt.date(*months[-1], 1)
    artifact = {
        "version": f"logreg-{dt.date.today():%Y%m%d}",
        "trained_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "label": f"(departures delayed >=15 min + cancelled) / scheduled >= {LABEL_THRESHOLD} "
        f"for an airport-local-hour with >= {MIN_FLIGHTS} departures",
        "features": FEATURES,
        "mean": scaler.mean_.round(6).tolist(),
        "scale": scaler.scale_.round(6).tolist(),
        "coef": logit.coef_[0].round(6).tolist(),
        "intercept": round(float(logit.intercept_[0]), 6),
        "airport_baseline": {k: round(v, 5) for k, v in baseline.items()},
        "train_period": [str(first), str(cutoff - dt.timedelta(days=1))],
        "test_period": [
            str(cutoff),
            str(dt.date(last.year + (last.month == 12), last.month % 12 + 1, 1) - dt.timedelta(days=1)),
        ],
        "metrics": {
            "test": results,
            "n_train": int(tr.sum()),
            "n_test": int(te.sum()),
            "positive_rate_train": round(float(y[tr].mean()), 4),
            "positive_rate_test": round(float(y[te].mean()), 4),
            "beats_baseline": bool(beats),
            "rule": "served only if logistic test ROC AUC >= baseline + 0.02",
        },
        "limitations": [
            "Predicts disruption of an airport-hour, not of any specific flight.",
            "No FAA advisory history is available, so programs in effect are not features.",
            "METAR history from IEM (redistributed NWS/FAA observations); TAF not used in training.",
            "Trained on BTS reporting carriers' scheduled domestic departures only.",
        ],
    }
    ARTIFACT.write_text(json.dumps(artifact, indent=1) + "\n")
    coef = sorted(zip(FEATURES, artifact["coef"], strict=True), key=lambda x: -abs(x[1]))
    lines = [
        "# Disruption risk model — validation report",
        "",
        f"Generated {artifact['trained_at']} by `pipelines/historical/train_risk_model.py`. All numbers below are",
        "computed on held-out data; nothing is hand-entered.",
        "",
        f"* **Label:** {artifact['label']}",
        f"* **Train:** {artifact['train_period'][0]} → {artifact['train_period'][1]} ({artifact['metrics']['n_train']:,} airport-hours, "
        f"{artifact['metrics']['positive_rate_train']:.1%} disrupted)",
        f"* **Test (chronological hold-out):** {artifact['test_period'][0]} → {artifact['test_period'][1]} "
        f"({artifact['metrics']['n_test']:,} airport-hours, {artifact['metrics']['positive_rate_test']:.1%} disrupted)",
        "",
        "| Model | ROC AUC | PR AUC | Brier | Log loss |",
        "|---|---|---|---|---|",
        *[
            f"| {name} | {m['roc_auc']} | {m['pr_auc']} | {m['brier']} | {m['log_loss']} |"
            for name, m in results.items()
        ],
        "",
        f"**Served:** {'logistic regression (beats baseline by ≥ 0.02 AUC)' if beats else 'no model — rules baseline only (logistic did not beat the baseline by 0.02 AUC)'}.",
        "",
        "## Standardised logistic coefficients (largest first)",
        "",
        "| Feature | Coefficient |",
        "|---|---|",
        *[f"| {f} | {c:+.3f} |" for f, c in coef],
        "",
        "Coefficients describe association in the training data, not causation.",
        "",
        "## Limitations",
        "",
        *[f"* {x}" for x in artifact["limitations"]],
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(json.dumps({"results": results, "beats_baseline": beats, "n_train": int(tr.sum()), "n_test": int(te.sum())}))


if __name__ == "__main__":
    main()
