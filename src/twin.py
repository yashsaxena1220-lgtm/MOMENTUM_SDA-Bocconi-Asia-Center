"""
The patient's digital twin.

Given a patient's record, recent watch data and their city's air and weather, the twin returns
  1. flare-up risk for the next 3 days (hybrid engine: learned body-signal model x published PM2.5 effect),
  2. how much each trigger pushes that risk up or down,
  3. transparent rule checks against the patient's own normal, and
  4. what-if answers, including full "Twin Lab" re-scoring when any input is changed.
"""
import numpy as np
import pandas as pd

from config import cal
from engine import predict, explain, load
from features import build_feature_table

TYPICAL_SD = {"hr": 4.9, "rr": 1.2, "spo2": 1.0, "steps": 1500, "sleep": 0.7}
SIGNAL_COL = {"hr": "heart_rate_bpm", "rr": "resp_rate_bpm", "spo2": "spo2_pct", "steps": "steps", "sleep": "sleep_hours"}


def threshold():
    return load()[1]["alert_threshold"]


def risk_level(prob, thr=None):
    thr = thr or threshold()
    return "High" if prob >= thr else "Medium" if prob >= thr * 0.5 else "Low"


def apply_manual_baseline(f, manual):
    """For a newly added patient with under ~2 weeks of data, use the normals the doctor entered."""
    if not manual:
        return f
    f = f.copy()
    for s, col in SIGNAL_COL.items():
        v = manual.get(s)
        if v is None:
            continue
        miss = f[f"{s}_normal"].isna()
        last3 = f[col].rolling(3, min_periods=1).mean()
        f.loc[miss, f"{s}_normal"] = v
        f.loc[miss, f"{s}_dev1"] = f.loc[miss, col] - v
        f.loc[miss, f"{s}_dev3"] = last3[miss] - v
        f.loc[miss, f"{s}_z3"] = (last3[miss] - v) / TYPICAL_SD[s]
    return f


def feature_table(patient, wear_hist, env_city, manual=None):
    f = build_feature_table(wear_hist, pd.DataFrame([patient]), env_city)
    return apply_manual_baseline(f, manual)


# ---------------------------------------------------------------- rule layer
def _worst(v, s, sign):
    """The more worrying of today's change and the 3-day average change (sign +1: higher is worse)."""
    opts = [(v.get(f"{s}_dev1"), "today"), (v.get(f"{s}_dev3"), "over 3 days")]
    opts = [(x, when) for x, when in opts if x is not None and pd.notna(x)]
    return max(opts, key=lambda o: sign * o[0]) if opts else (0.0, "")


def rule_checks(v):
    """v: dict-like with the latest values. Thresholds sit just inside published average changes
    (config.CALIBRATION); they are not validated clinical cut-offs. Each signal is checked on today's
    change and on the 3-day average, so the checks agree with the reading cards."""
    out = []
    d, when = _worst(v, "rr", +1)
    if d >= 3:
        out.append(("warning", f"Breathing {d:+.1f}/min above own normal ({when})"))
    d, when = _worst(v, "spo2", -1)
    if d <= -2:
        out.append(("warning", f"Oxygen {d:+.1f} points below own normal ({when})"))
    if pd.notna(v.get("spo2_now")) and v.get("spo2_now", 99) < 90:
        out.append(("urgent", f"Oxygen {v['spo2_now']:.0f}% today, below 90%"))
    d, when = _worst(v, "hr", +1)
    if d >= 7:
        out.append(("warning", f"Resting heart rate {d:+.0f} bpm above own normal ({when})"))
    if v.get("rescue_3d_vs_normal", 0) >= 1.5:
        out.append(("warning", f"Rescue inhaler {v['rescue_3d_vs_normal']:+.1f} puffs/day above normal"))
    if v.get("prescribed", 0) and v.get("adherence_7d", 1) <= 0.7:
        out.append(("watch", f"Took only {v['adherence_7d']:.0%} of controller doses this week"))
    if v.get("pm25", 0) >= 250:
        out.append(("watch", f"Severe air pollution (PM2.5 {v['pm25']:.0f} µg/m³)"))
    if v.get("temp_drop_21d", 0) >= 12:
        out.append(("watch", f"Temperature fell {v['temp_drop_21d']:.0f} C in total over 3 weeks"))
    return out


def record_text(r):
    """Plain summary of the health-record factors that raise flare-up risk."""
    bits = [f"GOLD {int(r.gold_stage)}"]
    if r.exacerbations_prior_year >= 1:
        bits.append(f"{int(r.exacerbations_prior_year)} flare-up{'s' if r.exacerbations_prior_year > 1 else ''} last year")
    if r.age >= 75:
        bits.append(f"age {int(r.age)}")
    if r.blood_eosinophils_per_ul >= 300:
        bits.append(f"high eosinophils ({int(r.blood_eosinophils_per_ul)}/µL)")
    if r.smoker_current:
        bits.append("still smoking")
    if r.biomass_fuel_exposure:
        bits.append("cooking smoke at home")
    if r.comorbidity_count >= 2:
        bits.append(f"{int(r.comorbidity_count)} other conditions")
    return "Health record: " + ", ".join(bits)


def trigger_text(group, r):
    t = {
        "Breathing rate": f"Breathing {r.rr_dev3:+.1f}/min vs own normal of {r.rr_normal:.1f}",
        "Heart rate": f"Resting heart rate {r.hr_dev3:+.0f} bpm vs own normal of {r.hr_normal:.0f}",
        "Blood oxygen": f"Oxygen {r.spo2_dev3:+.1f} points vs own normal of {r.spo2_normal:.1f}%",
        "Activity": f"Steps {r.steps_dev3:+.0f}/day vs own normal of {r.steps_normal:.0f}",
        "Sleep": f"Sleep {r.sleep_dev3:+.1f} h vs own normal",
        "Rescue inhaler use": f"Rescue inhaler {r.rescue_3d_vs_normal:+.1f} puffs/day vs normal",
        "Missed inhaler doses": f"Took {r.adherence_7d:.0%} of controller doses this week",
        "Air pollution (PM2.5)": f"PM2.5 averaged {r.pm25_lag2_7:.0f} µg/m³ over the past week",
        "Cold snap": f"Temperature fell {r.temp_drop_21d:.0f} C in total over 3 weeks; night low {r.temp_min_c:.0f} C",
        "Humidity / heat": f"Humidity {r.humidity_pct:.0f}%" + (" with heat" if r.humid_heat else ""),
        "Clinical history": record_text(r),
    }
    return t.get(group, group)


def score_row(row: pd.Series):
    """Risk and trigger pushes for one feature row (used by the dashboard and the Twin Lab)."""
    X = pd.DataFrame([row])
    prob = float(predict(X)[0])
    base, groups = explain(X)
    return prob, base, groups


def assess(patient, wear_hist, env_city, manual_baseline=None):
    f = feature_table(patient, wear_hist, env_city, manual_baseline)
    r = f.iloc[-1]
    prob, base, groups = score_row(r)
    triggers = [{"group": g, "push": v, "text": trigger_text(g, r)}
                for g, v in sorted(groups.items(), key=lambda kv: -kv[1]) if v > 0.05][:4]
    vals = dict(r)
    vals.update(spo2_now=r.spo2_pct, prescribed=r.controller_doses_prescribed)
    frac = cal("indoor_pm_fraction_with_purifier")
    scen = {
        "Stay indoors with an air purifier": score_row(r.copy().pipe(_set, pm25=r.pm25 * frac, pm25_lag2_7=r.pm25_lag2_7 * frac))[0],
        "Take every inhaler dose": score_row(r.copy().pipe(_set, adherence_7d=1.0))[0],
    }
    scen["Both"] = score_row(r.copy().pipe(_set, pm25=r.pm25 * frac, pm25_lag2_7=r.pm25_lag2_7 * frac, adherence_7d=1.0))[0]
    return {"prob": prob, "level": risk_level(prob), "threshold": threshold(), "groups": groups, "base": base,
            "triggers": triggers, "rules": rule_checks(vals), "scenarios": scen, "features": f, "row": r}


def _set(s, **kw):
    for k, v in kw.items():
        s[k] = v
    return s


def sweep(row, col, values, linked=None):
    """Risk as one input moves across a range (others held). linked: extra columns moved together."""
    X = pd.DataFrame([row] * len(values)).reset_index(drop=True)
    X[col] = values
    for c, fn in (linked or {}).items():
        X[c] = fn(np.asarray(values))
    return predict(X)


def score_history(patient, wear_hist, env_city):
    f = feature_table(patient, wear_hist, env_city)
    f["risk"] = predict(f)
    return f
