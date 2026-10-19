"""
Stress test on REAL, de-identified patients: MIMIC-III Clinical Database Demo v1.4 (100 patients, ODbL 1.0).

The twin was trained on simulated patients. This script feeds it real people it has never seen, of both
sexes and every adult age group, and checks five things:

  1. Robustness  : it runs for every real patient, with missing and extreme readings, and always returns a valid risk.
  2. Fairness    : risk and alert rates by sex and by age group (sex is not a model input, age is).
  3. Realism     : real vital signs compared with the simulated cohort's watch readings.
  4. Signal      : does a worsening of breathing, heart rate and oxygen in a real ICU stay raise the twin's risk,
                   and is the risk higher in patients who later died in hospital? (A different event from a COPD
                   flare-up, used only as a rough real-world check of the direction of the signal.)
  5. Edge cases  : missing oxygen sensor, very low oxygen, very fast breathing, youngest and oldest ages.

How a real patient becomes a twin input (same method as the dashboard's "Check a new person" page):
  usual readings = median of the first 24 h in the ICU; readings now = median of hours 24-48.
  Health record from ICD-9 codes: COPD, hypertension, diabetes, heart disease, heart failure, anaemia,
  obesity, smoking, home oxygen. Fields MIMIC does not hold (GOLD stage, eosinophils, BMI, cooking smoke,
  flu vaccine, steps, sleep, inhaler use) are set to neutral cohort values, so differences between real
  people come only from their real record and real vital signs. Air and weather are held fixed (one real
  Bengaluru day) for everyone, so the environment cannot explain any difference.

Input : data/raw/mimic3_demo/*.csv (extracted from the PhysioNet MIMIC-III demo, see data/raw/mimic3_demo/README.md)
Output: outputs/stress_test_real.csv (one row per real patient, no dates or names)
        outputs/stress_test_summary.json
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from config import RAW, PROCESSED, OUTPUTS
from twin import assess, threshold

SRC = RAW / "mimic3_demo"
ENV_CITY, ENV_DAY = "Bengaluru", pd.Timestamp("2019-11-05")
AGE_BANDS = [18, 40, 50, 60, 70, 80, 120]
AGE_LABELS = ["18-39", "40-49", "50-59", "60-69", "70-79", "80+"]
ICD = {
    "copd": r"^(491|492|496)", "copd_exacerbation": r"^4912[12]", "hypertension": r"^40[1-5]",
    "diabetes": r"^250", "ischemic_heart_disease": r"^41[0-4]", "heart_failure": r"^428", "anemia": r"^28[0-5]",
    "obesity": r"^2780", "smoker_current": r"^3051", "smoker_former": r"^V1582", "home_oxygen": r"^V462",
}


def feed(usual, now, end_day, city, n_days=45, pid="REAL"):
    """Daily rows: 42 days at the usual values with normal wobble, then 3 days at the readings now
    (identical to the dashboard's feed_from_readings)."""
    rng = np.random.default_rng(7)
    sd = {"hr": 3.0, "rr": 0.8, "spo2": 0.6, "steps": 0.15, "puffs": 0.3, "sleep": 0.5}
    vals = {}
    for k, u in usual.items():
        v = np.clip(u + rng.normal(0, sd[k], n_days) * (u if k == "steps" else 1), 0, None)
        v[-3:] = now[k]
        vals[k] = v
    return pd.DataFrame({"patient_id": pid, "date": pd.date_range(end=end_day, periods=n_days), "city": city,
                         "heart_rate_bpm": vals["hr"], "resp_rate_bpm": vals["rr"], "spo2_pct": np.clip(vals["spo2"], 0, 100),
                         "steps": vals["steps"], "sleep_hours": vals["sleep"], "systolic_bp": np.nan, "diastolic_bp": np.nan,
                         "rescue_puffs": vals["puffs"], "controller_doses_taken": 2.0, "controller_doses_prescribed": 2})


NEUTRAL_BODY = {"steps": 3000.0, "sleep": 7.0, "puffs": 1.0}


def load_real():
    pats = pd.read_csv(SRC / "patients.csv")
    adm = pd.read_csv(SRC / "admissions.csv")
    icu = pd.read_csv(SRC / "icustays.csv")
    dx = pd.read_csv(SRC / "diagnoses_icd.csv", dtype={"icd9_code": str})
    vit = pd.read_csv(SRC / "vitals.csv.gz")
    # remove impossible readings (charting errors), keep everything physiologically possible
    ok = {"hr": (20, 250), "rr": (4, 70), "spo2": (50, 100)}
    vit = vit[[ok[s][0] <= v <= ok[s][1] for s, v in zip(vit.signal, vit.value)]]

    first = icu.sort_values("intime").groupby("subject_id").first().reset_index()
    first = first.merge(adm[["hadm_id", "admittime", "deathtime", "hospital_expire_flag"]], on="hadm_id")
    first = first.merge(pats[["subject_id", "gender", "dob"]], on="subject_id")
    # ages above 89 are shifted to ~300 in MIMIC for privacy; they are shown as 90
    first["age"] = ((first.admittime - first.dob) / 86400 / 365.25).clip(upper=90).round().astype(int)
    for k, rx in ICD.items():
        first[k] = first.subject_id.isin(dx[dx.icd9_code.str.match(rx, na=False)].subject_id).astype(int)
    first["died_after_48h"] = ((first.hospital_expire_flag == 1)
                               & (((first.deathtime - first.intime) / 3600) > 48)).astype(int)
    first["died_within_48h"] = ((first.hospital_expire_flag == 1) & ~first.died_after_48h.astype(bool)).astype(int)

    v = vit[vit.icustay_id.isin(first.icustay_id)]
    usual = v[v.hours_from_icu_admit.between(0, 24)].pivot_table(index="icustay_id", columns="signal", values="value", aggfunc="median")
    now = v[v.hours_from_icu_admit.between(24, 48, inclusive="right")].pivot_table(index="icustay_id", columns="signal", values="value", aggfunc="median")
    first = first.join(usual.add_prefix("usual_"), on="icustay_id").join(now.add_prefix("now_"), on="icustay_id")
    first["readings"] = first.icustay_id.map(v.groupby("icustay_id").size()).fillna(0).astype(int)
    return first, vit


def record(r, cohort):
    return {"patient_id": f"REAL-{int(r.subject_id)}", "age": int(r.age), "sex": r.gender, "city": ENV_CITY,
            "gold_stage": 2, "exacerbations_prior_year": 0, "biomass_fuel_exposure": 0,
            "smoking_status": "current" if r.smoker_current else ("former" if r.smoker_former else "never"),
            "blood_eosinophils_per_ul": float(cohort.blood_eosinophils_per_ul.median()), "influenza_vaccinated": 0,
            "home_oxygen": int(r.home_oxygen), "bmi": float(cohort.bmi.median()),
            **{k: int(r[k]) for k in ["hypertension", "diabetes", "ischemic_heart_disease", "heart_failure", "anemia", "obesity"]}}


def run_one(rec, usual, now, env):
    res = assess(rec, feed({**usual, **NEUTRAL_BODY}, {**now, **NEUTRAL_BODY}, ENV_DAY, ENV_CITY, pid=rec["patient_id"]),
                 env, manual_baseline=usual)
    return res


def main():
    env = pd.read_csv(PROCESSED / "environment_daily.csv", parse_dates=["date"])
    env = env[(env.city == ENV_CITY) & (env.date <= ENV_DAY)]
    cohort = pd.read_csv(PROCESSED / "patients.csv")
    real, vit = load_real()
    thr = threshold()

    rows, errors = [], []
    for _, r in real.iterrows():
        complete = all(pd.notna(getattr(r, f"{w}_{s}")) for w in ("usual", "now") for s in ("hr", "rr", "spo2"))
        if not complete:
            rows.append({"subject_id": r.subject_id, "status": "skipped: under 48 h of ICU vitals"})
            continue
        usual = {"hr": r.usual_hr, "rr": r.usual_rr, "spo2": r.usual_spo2}
        now = {"hr": r.now_hr, "rr": r.now_rr, "spo2": r.now_spo2}
        try:
            res = run_one(record(r, cohort), usual, now, env)
            ok = np.isfinite(res["prob"]) and 0 <= res["prob"] <= 1
            rows.append({"subject_id": r.subject_id, "status": "ok" if ok else "invalid output", "risk": res["prob"],
                         "level": res["level"], "alert": int(res["prob"] >= thr or res["level"] == "Urgent"), "rule_checks": len(res["rules"]),
                         "top_reason": res["triggers"][0]["group"] if res["triggers"] else ""})
        except Exception as e:  # a crash is a finding, not a stop
            errors.append(f"{r.subject_id}: {type(e).__name__}: {e}")
            rows.append({"subject_id": r.subject_id, "status": f"error: {type(e).__name__}"})

    out = real.merge(pd.DataFrame(rows), on="subject_id")
    out["sex"] = out.gender.map({"M": "Male", "F": "Female"})
    out["age_group"] = pd.cut(out.age, AGE_BANDS, labels=AGE_LABELS, right=False)
    for s in ("hr", "rr", "spo2"):
        out[f"change_{s}"] = out[f"now_{s}"] - out[f"usual_{s}"]
    out["worsening_signs"] = ((out.change_rr >= 3).astype(int) + (out.change_hr >= 7).astype(int)
                              + (out.change_spo2 <= -2).astype(int))
    ran = out[out.status == "ok"].copy()

    # ---- 2. fairness
    def grp(col):
        g = ran.groupby(col, observed=True)
        return pd.DataFrame({"patients": g.size(), "median_risk": g.risk.median().round(3),
                             "alert_rate": g.alert.mean().round(2), "worsening_rate": (g.worsening_signs.mean()).round(2)})
    by_sex, by_age = grp("sex"), grp("age_group")
    # like-for-like: alert rate by sex among patients showing the same number of warning signs
    by_sex_signs = []
    for k, g in ran.groupby("worsening_signs"):
        row = {"warning_signs": int(k)}
        for s in ("Female", "Male"):
            gs = g[g.sex == s]
            row[f"{s}_patients"] = int(len(gs))
            row[f"{s}_alert_rate"] = round(float(gs.alert.mean()), 2) if len(gs) else None
        by_sex_signs.append(row)

    # ---- 3. realism: real usual vitals vs simulated watch readings (per-patient medians)
    w = pd.read_csv(PROCESSED / "wearables_daily.csv", usecols=["patient_id", "heart_rate_bpm", "resp_rate_bpm", "spo2_pct"])
    sim = w.groupby("patient_id").median()
    realism = pd.DataFrame({
        "Real ICU patients (median of first 24 h)": [ran.usual_hr.median(), ran.usual_rr.median(), ran.usual_spo2.median()],
        "Simulated COPD cohort (median daily reading)": [sim.heart_rate_bpm.median(), sim.resp_rate_bpm.median(), sim.spo2_pct.median()],
    }, index=["Heart rate (bpm)", "Breathing rate (/min)", "SpO2 (%)"]).round(1)

    # ---- 4. signal
    surv = ran[ran.died_within_48h == 0]
    corr = float(ran[["risk", "worsening_signs"]].corr(method="spearman").iloc[0, 1])
    auc_death = float(roc_auc_score(surv.died_after_48h, surv.risk)) if surv.died_after_48h.nunique() == 2 else None

    # ---- 5. edge cases (one real median patient, perturbed)
    base = ran.loc[(ran.risk - ran.risk.median()).abs().idxmin()]
    rec0 = record(real[real.subject_id == base.subject_id].iloc[0], cohort)
    u0 = {"hr": base.usual_hr, "rr": base.usual_rr, "spo2": base.usual_spo2}
    cases = {
        "Real readings, unchanged": (rec0, u0, dict(u0)),
        "No oxygen sensor (SpO2 missing)": (rec0, {**u0, "spo2": np.nan}, {**u0, "spo2": np.nan}),
        "Oxygen falls to 82%": (rec0, u0, {**u0, "spo2": 82.0}),
        "Breathing rises to 35/min": (rec0, u0, {**u0, "rr": 35.0}),
        "All three signs worsen": (rec0, u0, {"hr": u0["hr"] + 15, "rr": u0["rr"] + 8, "spo2": u0["spo2"] - 5}),
        "Age 18": ({**rec0, "age": 18}, u0, dict(u0)),
        "Age 90": ({**rec0, "age": 90}, u0, dict(u0)),
        "Sex switched": ({**rec0, "sex": "F" if rec0["sex"] == "M" else "M"}, u0, dict(u0)),
    }
    edge = []
    for name, (rec, u, n) in cases.items():
        try:
            res = run_one(rec, u, n, env)
            edge.append({"case": name, "risk": round(res["prob"], 3), "level": res["level"], "rule_checks": len(res["rules"]), "result": "ok"})
        except Exception as e:
            edge.append({"case": name, "risk": None, "level": "", "rule_checks": None, "result": f"error: {type(e).__name__}"})
    edge = pd.DataFrame(edge)
    worse = edge.set_index("case").risk
    monotonic = bool(worse["All three signs worsen"] > worse["Real readings, unchanged"]
                     and worse["Oxygen falls to 82%"] > worse["Real readings, unchanged"]
                     and worse["Breathing rises to 35/min"] > worse["Real readings, unchanged"])

    summary = {
        "dataset": "MIMIC-III Clinical Database Demo v1.4 (PhysioNet, ODbL 1.0), 100 de-identified ICU patients, Beth Israel Deaconess Medical Center, Boston",
        "real_patients": int(len(out)), "real_vital_readings": int(len(vit)),
        "assessed": int(len(ran)), "skipped_short_stay": int(out.status.str.startswith("skipped").sum()),
        "errors": len(errors), "invalid_outputs": int((out.status == "invalid output").sum()),
        "sex_mix": out.sex.value_counts().to_dict(), "age_mix": out.age_group.value_counts().sort_index().astype(int).to_dict(),
        "copd_patients": int(out.copd.sum()), "copd_assessed": int(ran.copy().copd.sum()),
        "risk_range": [round(float(ran.risk.min()), 3), round(float(ran.risk.max()), 3)],
        "by_sex": by_sex.reset_index().to_dict("records"), "by_age_group": by_age.reset_index().astype({"age_group": str}).to_dict("records"),
        "by_sex_same_warning_signs": by_sex_signs,
        "realism": realism.reset_index().rename(columns={"index": "signal"}).to_dict("records"),
        "spearman_risk_vs_worsening_signs": round(corr, 2),
        "auroc_risk_for_later_in_hospital_death": round(auc_death, 2) if auc_death else None,
        "deaths_after_48h": int(surv.died_after_48h.sum()), "survivors": int((surv.died_after_48h == 0).sum()),
        "median_risk_copd_vs_not": [round(float(ran[ran.copd == 1].risk.median()), 3), round(float(ran[ran.copd == 0].risk.median()), 3)],
        "edge_cases": edge.to_dict("records"), "edge_cases_direction_correct": monotonic,
        "alert_threshold": round(thr, 3), "error_messages": errors[:10],
        "caveat": "Real ICU patients are not a COPD home-monitoring cohort, and in-hospital death is not a COPD flare-up. "
                  "This tests robustness, fairness and the direction of the signal on real people; it is not clinical validation.",
    }
    OUTPUTS.mkdir(exist_ok=True)
    keep = ["subject_id", "sex", "age", "age_group", "copd", "hypertension", "diabetes", "heart_failure", "status",
            "usual_hr", "now_hr", "usual_rr", "now_rr", "usual_spo2", "now_spo2", "worsening_signs", "risk", "level", "alert",
            "rule_checks", "top_reason", "died_after_48h"]
    out[keep].round(3).to_csv(OUTPUTS / "stress_test_real.csv", index=False)
    json.dump(summary, open(OUTPUTS / "stress_test_summary.json", "w"), indent=2, default=str)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("edge_cases",)}, indent=1, default=str))
    print(edge.to_string(index=False))


if __name__ == "__main__":
    main()
