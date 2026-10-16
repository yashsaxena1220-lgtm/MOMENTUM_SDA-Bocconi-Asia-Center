"""
Turn the three streams into model features, day by day, using only information
available up to that day (no peeking at the future).

The core idea of the twin: compare today's readings with the patient's OWN normal,
learned from their recent history, not with a textbook range.
"""
import numpy as np
import pandas as pd

SIGNALS = {"heart_rate_bpm": "hr", "resp_rate_bpm": "rr", "spo2_pct": "spo2", "steps": "steps", "sleep_hours": "sleep"}
BASELINE_WINDOW = (28, 8)      # personal normal = days t-28 .. t-8 (skips the most recent week)

EHR_FEATURES = ["age", "gold_stage", "exacerbations_prior_year", "biomass_fuel_exposure", "smoker_current",
                "blood_eosinophils_per_ul", "comorbidity_count", "influenza_vaccinated", "home_oxygen", "bmi"]
ENV_FEATURES = ["pm25", "pm25_lag2_7", "temp_drop_21d", "temp_min_c", "humidity_pct", "humid_heat"]

FEATURE_GROUPS = {
    "Breathing rate": ["rr_dev1", "rr_dev3", "rr_z3"],
    "Heart rate": ["hr_dev1", "hr_dev3", "hr_z3"],
    "Blood oxygen": ["spo2_dev1", "spo2_dev3", "spo2_z3"],
    "Activity": ["steps_dev3", "steps_z3"],
    "Sleep": ["sleep_dev3"],
    "Rescue inhaler use": ["rescue_3d_vs_normal"],
    "Missed inhaler doses": ["adherence_7d"],
    "Air pollution (PM2.5)": ["pm25", "pm25_lag2_7"],
    "Cold snap": ["temp_drop_21d", "temp_min_c"],
    "Humidity / heat": ["humidity_pct", "humid_heat"],
    "Clinical history": EHR_FEATURES,
}
STREAM_OF_GROUP = {
    "Breathing rate": "wearable", "Heart rate": "wearable", "Blood oxygen": "wearable", "Activity": "wearable",
    "Sleep": "wearable", "Rescue inhaler use": "wearable", "Missed inhaler doses": "wearable",
    "Air pollution (PM2.5)": "environment", "Cold snap": "environment", "Humidity / heat": "environment",
    "Clinical history": "ehr",
}


def patient_static(patients):
    p = patients.copy()
    p["smoker_current"] = (p.smoking_status == "current").astype(int)
    comorb = [c for c in ["hypertension", "diabetes", "ischemic_heart_disease", "heart_failure", "anemia", "obesity"] if c in p]
    p["comorbidity_count"] = p[comorb].sum(axis=1)
    return p[["patient_id"] + EHR_FEATURES]


def wearable_features(w):
    """w: one or many patients' daily rows, sorted by date."""
    w = w.sort_values(["patient_id", "date"]).copy()
    g = w.groupby("patient_id")
    lo, hi = BASELINE_WINDOW
    for col, s in SIGNALS.items():
        hist = g[col].transform(lambda x: x.shift(hi).rolling(lo - hi + 1, min_periods=10).median())
        spread = g[col].transform(lambda x: x.shift(hi).rolling(lo - hi + 1, min_periods=10).std())
        last3 = g[col].transform(lambda x: x.rolling(3, min_periods=1).mean())
        w[f"{s}_normal"] = hist
        w[f"{s}_dev1"] = w[col] - hist
        w[f"{s}_dev3"] = last3 - hist
        w[f"{s}_z3"] = (last3 - hist) / spread.clip(lower=1e-3 if s != "steps" else 300)
    w["rescue_3d_vs_normal"] = (g.rescue_puffs.transform(lambda x: x.rolling(3, min_periods=1).mean())
                                - g.rescue_puffs.transform(lambda x: x.shift(hi).rolling(lo - hi + 1, min_periods=10).mean()))
    prescribed = w.controller_doses_prescribed.replace(0, np.nan)
    w["adherence_7d"] = (g.controller_doses_taken.transform(lambda x: x.rolling(7, min_periods=1).sum())
                         / (7 * prescribed)).fillna(1.0).clip(0, 1)
    if "in_exacerbation" in w:
        last_end = w.date.where(w.in_exacerbation.eq(1)).groupby(w.patient_id).transform(lambda x: x.shift(1).ffill())
        w["days_since_last_flare"] = (w.date - last_end).dt.days.fillna(365).clip(upper=365)
    else:
        w["days_since_last_flare"] = 365
    return w


def environment_features(env):
    env = env.sort_values(["city", "date"]).copy()
    g = env.groupby("city")
    env["pm25_lag2_7"] = g.pm25.transform(lambda s: s.shift(2).rolling(6, min_periods=1).mean()).fillna(env.pm25)
    env["temp_drop_21d"] = np.clip(-env.temp_change_c.fillna(0), 0, None).groupby(env.city).transform(
        lambda s: s.rolling(21, min_periods=1).sum())
    env["humid_heat"] = ((env.humidity_pct >= 80) & (env.temp_mean_c >= 28)).astype(int)
    return env[["city", "date"] + ENV_FEATURES]


def build_feature_table(wearables, patients, env):
    f = wearable_features(wearables)
    f = f.merge(environment_features(env), on=["city", "date"], how="left")
    f = f.merge(patient_static(patients), on="patient_id", how="left")
    return f


def model_feature_names():
    return [c for grp in FEATURE_GROUPS.values() for c in grp]
