"""Optional trained model (logistic regression) served alongside the rules baseline.

The model artifact (``app/data/risk_model.json``) is produced by
``pipelines/historical/train_risk_model.py`` and contains standardisation parameters,
coefficients, validated metrics and training periods. If the artifact is absent, or its
validation did not beat the baseline, no model output is served.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ARTIFACT = Path(__file__).resolve().parents[1] / "data" / "risk_model.json"


@dataclass(frozen=True, slots=True)
class ModelOutput:
    probability: float
    contributions: list[dict[str, Any]]


def _features(
    row: dict[str, Any], local: dt.datetime, baseline: float | None
) -> dict[str, float] | None:
    """Live-time features; must mirror train_risk_model.build_features exactly."""
    vis = row.get("visibility_sm")
    if row.get("weather_observed_at") is None or vis is None:
        return None
    ceiling = row.get("ceiling_ft")
    wx = (row.get("wx_string") or "").upper()
    return {
        "low_visibility": 1.0 if float(vis) < 3 else 0.0,
        "very_low_visibility": 1.0 if float(vis) < 1 else 0.0,
        "low_ceiling": 1.0 if ceiling is not None and ceiling < 1000 else 0.0,
        "wind_kt": float(row.get("wind_speed_kt") or 0),
        "gust_kt": float(row.get("wind_gust_kt") or 0),
        "thunderstorm": 1.0 if "TS" in wx else 0.0,
        "snow_or_freezing": 1.0 if ("SN" in wx or "FZ" in wx) else 0.0,
        "rain": 1.0 if "RA" in wx else 0.0,
        "hour_sin": math.sin(2 * math.pi * local.hour / 24),
        "hour_cos": math.cos(2 * math.pi * local.hour / 24),
        "month_sin": math.sin(2 * math.pi * local.month / 12),
        "month_cos": math.cos(2 * math.pi * local.month / 12),
        "weekend": 1.0 if local.isoweekday() >= 6 else 0.0,
        "airport_baseline": baseline if baseline is not None else math.nan,
    }


class RiskModel:
    def __init__(self, artifact: dict[str, Any]) -> None:
        self.version: str = artifact["version"]
        self.features: list[str] = artifact["features"]
        self.mean: list[float] = artifact["mean"]
        self.scale: list[float] = artifact["scale"]
        self.coef: list[float] = artifact["coef"]
        self.intercept: float = artifact["intercept"]
        self.baselines: dict[str, float] = artifact["airport_baseline"]
        self.metrics: dict[str, Any] = artifact["metrics"]
        self.artifact = artifact

    def predict(
        self, row: dict[str, Any], local: dt.datetime, airport: str, now: dt.datetime
    ) -> ModelOutput | None:
        feats = _features(row, local, self.baselines.get(airport))
        if feats is None or any(math.isnan(feats[f]) for f in self.features):
            return None
        z = [
            (feats[f] - m) / s for f, m, s in zip(self.features, self.mean, self.scale, strict=True)
        ]
        logit = self.intercept + sum(c * v for c, v in zip(self.coef, z, strict=True))
        prob = 1 / (1 + math.exp(-logit))
        contrib: list[dict[str, Any]] = sorted(
            (
                {
                    "feature": f,
                    "value": round(feats[f], 3),
                    "logit_contribution": round(c * v, 3),
                }
                for f, c, v in zip(self.features, self.coef, z, strict=True)
            ),
            key=lambda d: -abs(d["logit_contribution"]),
        )
        return ModelOutput(probability=round(prob, 4), contributions=contrib[:6])


@lru_cache
def load_model() -> RiskModel | None:
    if not ARTIFACT.exists():
        return None
    artifact = json.loads(ARTIFACT.read_text())
    if not artifact.get("metrics", {}).get("beats_baseline"):
        return None
    return RiskModel(artifact)


def model_card() -> dict[str, Any] | None:
    if not ARTIFACT.exists():
        return None
    a = json.loads(ARTIFACT.read_text())
    return {
        k: a[k]
        for k in (
            "version",
            "trained_at",
            "label",
            "features",
            "train_period",
            "test_period",
            "metrics",
            "limitations",
        )
        if k in a
    }
