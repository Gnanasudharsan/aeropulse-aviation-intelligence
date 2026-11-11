# Disruption risk model — validation report

Generated 2026-11-11T05:50:29+00:00 by `pipelines/historical/train_risk_model.py`. All numbers below are
computed on held-out data; nothing is hand-entered.

* **Label:** (departures delayed >=15 min + cancelled) / scheduled >= 0.35 for an airport-local-hour with >= 5 departures
* **Train:** 2024-09-01 → 2026-02-28 (412,917 airport-hours, 19.8% disrupted)
* **Test (chronological hold-out):** 2026-03-01 → 2026-08-31 (141,120 airport-hours, 29.9% disrupted)

| Model | ROC AUC | PR AUC | Brier | Log loss |
|---|---|---|---|---|
| baseline | 0.7822 | 0.5649 | 0.1826 | 0.5348 |
| logistic | 0.7873 | 0.5851 | 0.1715 | 0.5079 |
| hgb | 0.8113 | 0.6336 | 0.1616 | 0.4846 |

**Served:** no model — rules baseline only (logistic did not beat the baseline by 0.02 AUC).

## Standardised logistic coefficients (largest first)

| Feature | Coefficient |
|---|---|
| hour_sin | -0.953 |
| airport_baseline | +0.318 |
| snow_or_freezing | +0.209 |
| month_cos | -0.201 |
| thunderstorm | +0.180 |
| rain | +0.145 |
| weekend | +0.139 |
| low_visibility | +0.087 |
| wind_kt | +0.077 |
| hour_cos | +0.075 |
| gust_kt | +0.071 |
| low_ceiling | +0.069 |
| very_low_visibility | +0.064 |
| month_sin | +0.047 |

Coefficients describe association in the training data, not causation.

## Limitations

* Predicts disruption of an airport-hour, not of any specific flight.
* No FAA advisory history is available, so programs in effect are not features.
* METAR history from IEM (redistributed NWS/FAA observations); TAF not used in training.
* Trained on BTS reporting carriers' scheduled domestic departures only.
