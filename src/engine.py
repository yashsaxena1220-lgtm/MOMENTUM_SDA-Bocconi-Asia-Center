"""
Hybrid twin risk engine.

  risk = machine-learned risk from body signals, inhaler use, weather and health record
         x  published PM2.5 dose-response (DeVries 2017: +2.5% per 10 µg/m³)

Why hybrid: the body-signal patterns are complex and best learned from data, while the air-pollution
effect is small and well measured in large studies, so we take it from the literature instead of asking a
model trained on noisy daily data to rediscover it. Both parts combine on the odds scale, so every factor's
push on risk can be shown side by side.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

from config import MODELS, cal
from features import FEATURE_GROUPS, model_feature_names

PM_COLS = ["pm25", "pm25_lag2_7"]
GROUP_OF = {c: g for g, cols in FEATURE_GROUPS.items() for c in cols}


def ml_features():
    return [f for f in model_feature_names() if f not in PM_COLS]


def pm_multiplier(pm7):
    pm = cal("pm25_effect")
    x = np.clip(np.asarray(pm7, dtype=float) - pm["reference_ug"], 0, pm["cap_ug"] - pm["reference_ug"])
    return (1 + pm["pct_per_10ug"] / 100) ** (x / 10)


def combine(p_ml, pm7, norm):
    p_ml = np.clip(np.asarray(p_ml, dtype=float), 1e-6, 1 - 1e-6)
    odds = p_ml / (1 - p_ml) * pm_multiplier(pm7) / norm
    return odds / (1 + odds)


_cache = {}


def load():
    if "m" not in _cache:
        _cache["m"] = lgb.Booster(model_file=str(MODELS / "flare_risk_lgbm.txt"))
        _cache["meta"] = json.load(open(MODELS / "model_meta.json"))
    return _cache["m"], _cache["meta"]


def predict(X: pd.DataFrame):
    """Risk for every row of a feature table (needs ml_features() + pm25_lag2_7)."""
    m, meta = load()
    return combine(m.predict(X[meta["features"]]), X.pm25_lag2_7.values, meta["pm_norm"])


def explain(X_row: pd.DataFrame):
    """Push of each trigger group on the log-odds of risk for one row, plus the base value."""
    m, meta = load()
    c = m.predict(X_row[meta["features"]], pred_contrib=True)[0]
    base, parts = float(c[-1]), pd.Series(c[:-1], index=meta["features"])
    groups = parts.groupby(lambda f: GROUP_OF[f]).sum().to_dict()
    groups["Air pollution (PM2.5)"] = float(np.log(pm_multiplier(X_row.pm25_lag2_7.values[0]) / meta["pm_norm"]))
    return base, groups
