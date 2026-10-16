"""
Dynamic stream: simulated daily smartwatch, pulse-oximeter, BP-cuff and smart-inhaler
readings, plus the flare-up (exacerbation) events they lead up to.

No open dataset of COPD patients with wearables and labelled flare-ups exists, so this
stream is simulated. Every effect size comes from config.CALIBRATION, which cites its source.
Flare-up risk on each day depends on the patient's record (static stream) and on the
real air quality and weather of their city (environment stream).

Inputs : data/processed/patients.csv, data/processed/environment_daily.csv
Outputs: data/processed/wearables_daily.csv, data/processed/exacerbation_events.csv
"""
import numpy as np
import pandas as pd

from config import PROCESSED, SEED, cal

WEARABLE_COLS = ["heart_rate_bpm", "resp_rate_bpm", "spo2_pct", "steps", "sleep_hours",
                 "systolic_bp", "diastolic_bp"]


# ------------------------------------------------------------------ environment -> risk
def env_multipliers(env):
    """Daily flare-up risk multipliers from air quality and weather, per city (before patient sensitivity)."""
    env = env.sort_values(["city", "date"]).copy()
    pm = cal("pm25_effect")
    lagged = env.groupby("city").pm25.transform(
        lambda s: s.shift(pm["lag_start"]).rolling(pm["window_days"] - pm["lag_start"] + 1, min_periods=1).mean())
    lagged = lagged.fillna(env.pm25)
    excess = np.clip(lagged - pm["reference_ug"], 0, pm["cap_ug"] - pm["reference_ug"])
    env["m_pm25"] = (1 + pm["pct_per_10ug"] / 100) ** (excess / 10)

    td = cal("temperature_drop_effect")
    beta = np.log(td["cum_rr_21d"]) / (td["lag_days"] * td["drop_c"])     # per degree of drop, per lag day
    drop = np.clip(-env.temp_change_c.fillna(0), 0, None)
    drop_sum = drop.groupby(env.city).transform(lambda s: s.rolling(td["lag_days"], min_periods=1).sum())
    env["m_cold"] = np.exp(beta * drop_sum)

    hh = cal("humid_heat_effect")
    env["m_humid"] = np.where((env.humidity_pct >= hh["rh_threshold"]) & (env.temp_mean_c >= hh["temp_threshold"]),
                              hh["multiplier"], 1.0)
    return env


# ------------------------------------------------------------------ record -> risk
COMORBIDITIES = ["hypertension", "diabetes", "ischemic_heart_disease", "heart_failure", "anemia"]


def record_multiplier(p):
    """How much the health record raises or lowers this patient's yearly flare-up rate (before rescaling)."""
    eo = cal("eosinophil_effect")
    frac = np.clip((p.blood_eosinophils_per_ul - eo["low_ul"]) / (eo["high_ul"] - eo["low_ul"]), 0, 1)
    m = eo["multiplier_at_high"] ** frac
    if p.smoking_status == "current":
        m *= cal("current_smoking_effect")["multiplier"]
    if p.biomass_fuel_exposure:
        m *= cal("biomass_effect")["multiplier"]
    ag = cal("age_effect")
    m *= ag["per_decade"] ** ((p.age - ag["reference_age"]) / 10)
    m *= cal("comorbidity_effect")["per_condition"] ** sum(int(getattr(p, c, 0) or 0) for c in COMORBIDITIES)
    lb = cal("low_bmi_effect")
    if pd.notna(p.bmi) and p.bmi < lb["bmi_below"]:
        m *= lb["multiplier"]
    return float(m)


# ------------------------------------------------------------------ one patient
def _event_shifts(d, dur, prodrome):
    """Change from personal normal on day offset d relative to onset (d=0)."""
    rr, hr, sp, st = cal("resp_rate_rise"), cal("heart_rate_rise"), cal("spo2_drop"), cal("steps_drop_per_day")
    if d < -prodrome or d > dur + 3:
        return 0, 0, 0, 0, 0
    if d < 0:                                     # warning period
        frac = (d + prodrome + 1) / prodrome      # ramps up towards onset
        r = rr["day_minus_1"] if d == -1 else rr["day_minus_2"] if d == -2 else 0.8 * frac
        h = hr["prodrome_week"] + (hr["onset"] - hr["prodrome_week"]) * max(0, (d + 3) / 3)
        s = -sp["prodrome_week"] * frac - (sp["onset"] - sp["prodrome_week"]) * max(0, (d + 2) / 2)
        return r, h * frac ** 0.5, s, -st["prodrome"] * frac, 0.6 * frac
    decay = 1.0 if d <= dur else max(0.0, 1 - (d - dur) / 3)   # recovery over 3 days after the event
    return rr["onset"] * decay, hr["onset"] * decay, -sp["onset"] * decay, -st["during"] * decay, 1.5 * decay


def simulate_patient(p, env_city, rng, rec_norm=1.0):
    n = len(env_city)
    dates = env_city.date.values
    g = int(p.gold_stage)
    noise = cal("daily_noise_sd")

    # personal normal (the twin's baseline), anchored on the patient's Synthea vitals where present
    hr0 = p.heart_rate if 50 <= (p.heart_rate if pd.notna(p.heart_rate) else 0) <= 110 else rng.normal(78, 6)
    rr_syn = p.resp_rate if pd.notna(p.resp_rate) and 10 <= p.resp_rate <= 30 else 15.5
    rr0 = 0.5 * rr_syn + 0.5 * (15.0 + 0.8 * (g - 1)) + rng.normal(0, 0.8)
    sp0 = np.clip(96.5 - 0.9 * (g - 1) + rng.normal(0, 0.7), 88, 99)
    st0 = np.clip(rng.normal(5800 - 900 * (g - 1) - 40 * (p.age - 65), 1200), 800, 12000)
    sl0 = rng.normal(6.5, 0.6)
    sbp0 = p.systolic_bp if pd.notna(p.systolic_bp) else rng.normal(132, 15)
    dbp0 = p.diastolic_bp if pd.notna(p.diastolic_bp) else rng.normal(82, 9)
    puff0 = 0.3 * g

    # controller inhaler: 2 doses a day; habit drifts week to week
    prescribed = 2 if p.on_maintenance_inhaler else 0
    habit = np.clip(p.adherence_habit + np.repeat(rng.normal(0, 0.12, n // 7 + 1), 7)[:n], 0.02, 1)
    doses = rng.binomial(prescribed, habit) if prescribed else np.zeros(n, int)
    adh7 = pd.Series(doses / max(prescribed, 1)).rolling(7, min_periods=1).mean().values if prescribed else np.ones(n)

    # daily flare-up hazard
    rate = cal("exac_rate_per_year_by_stage")[g]
    # frequent exacerbators flare more, scaled so each stage's average still matches ECLIPSE
    hi, lo, share = cal("frequent_exacerbator_rate_multiplier"), 0.7, cal("frequent_exacerbator_share_by_stage")[g]
    rate *= (hi if p.frequent_exacerbator else lo) / (share * hi + (1 - share) * lo)
    rate *= record_multiplier(p) / rec_norm                   # health-record factors (config.CALIBRATION)
    frailty = rng.gamma(4, 0.25)                               # unexplained person-to-person variation
    m_env = (env_city.m_pm25.values ** p.pollution_sensitivity) * env_city.m_cold.values * env_city.m_humid.values
    m_adh = 1 + (cal("missed_dose_effect")["multiplier_at_zero_adherence"] - 1) * (1 - adh7)
    m_vac = cal("flu_vaccine_effect")["multiplier"] if p.influenza_vaccinated else 1.0
    hazard = rate / 365 * frailty * m_env / env_city.norm.values * m_adh * m_vac

    onsets, blocked_until = [], 7
    for t in range(n):
        if t >= blocked_until and rng.random() < min(hazard[t], 0.3):
            dur = int(np.clip(rng.lognormal(np.log(cal("event_duration_days")["median"]), cal("event_duration_days")["log_sd"]), 2, 30))
            onsets.append((t, dur, rng.integers(cal("prodrome_days")[0], cal("prodrome_days")[1] + 1),
                           rng.random() < cal("silent_event_share"), np.clip(rng.normal(1, 0.3), 0.4, 1.8)))
            blocked_until = t + dur + 4          # a new flare-up can start once the recovery tail is over

    d_rr, d_hr, d_sp, d_st, d_puff, in_ex = (np.zeros(n) for _ in range(6))
    for t0, dur, pro, silent, size in onsets:
        k = 0.2 if silent else size
        for t in range(max(0, t0 - pro), min(n, t0 + dur + 4)):
            r, h, s, st, pf = _event_shifts(t - t0, dur, pro)
            d_rr[t] += k * r; d_hr[t] += k * h; d_sp[t] += k * s; d_st[t] += size * st; d_puff[t] += pf
        in_ex[t0:t0 + dur + 3] = 1           # flare-up plus 3-day recovery tail (signals still off normal)
    # colds and bad days that look a little like warning signs but do not become a flare-up (ASSUMPTION)
    for _ in range(rng.poisson(2)):
        t, L = rng.integers(0, n), rng.integers(2, 6)
        d_rr[t:t + L] += rng.uniform(0.8, 2.0); d_hr[t:t + L] += rng.uniform(2, 5); d_puff[t:t + L] += 0.5

    pm = env_city.pm25.values
    heat = np.clip(env_city.temp_mean_c.values - 32, 0, None)
    w = pd.DataFrame({
        "patient_id": p.patient_id, "date": dates, "city": p.city,
        "heart_rate_bpm": hr0 + d_hr + rng.normal(0, noise["heart_rate"], n),
        "resp_rate_bpm": rr0 + d_rr + 0.003 * pm + rng.normal(0, noise["resp_rate"], n),
        "spo2_pct": sp0 + d_sp + rng.normal(0, noise["spo2"], n),
        "steps": np.clip(st0 + d_st, 200, None) * np.clip(1 - 0.03 * heat - 0.0003 * pm, 0.6, 1) * rng.lognormal(0, noise["steps_cv"], n),
        "sleep_hours": sl0 - 0.4 * (in_ex > 0) + rng.normal(0, 0.7, n),
        "systolic_bp": sbp0 + rng.normal(0, 8, n),
        "diastolic_bp": dbp0 + rng.normal(0, 5, n),
        "rescue_puffs": rng.poisson(np.clip(puff0 * (1 + 2 * d_puff), 0.02, None)),
        "controller_doses_taken": doses, "controller_doses_prescribed": prescribed,
    })
    w["resp_rate_bpm"] = w.resp_rate_bpm.clip(10, 40).round(1)
    w["heart_rate_bpm"] = w.heart_rate_bpm.clip(45, 150).round(0)
    w["spo2_pct"] = w.spo2_pct.clip(80, 100).round(1)
    w["steps"] = w.steps.clip(0, 25000).round(0)
    w["sleep_hours"] = w.sleep_hours.clip(2, 11).round(1)
    w[["systolic_bp", "diastolic_bp"]] = w[["systolic_bp", "diastolic_bp"]].round(0)

    onset = np.zeros(n, int); target = np.zeros(n, int)
    for t0, *_ in onsets:
        onset[t0] = 1
        target[max(0, t0 - 3):t0] = 1
    w["exacerbation_onset"], w["in_exacerbation"], w["onset_within_3d"] = onset, in_ex.astype(int), target

    # watch not worn: ~5% of days, mostly in short runs (ASSUMPTION)
    gaps = np.zeros(n, bool)
    for _ in range(rng.poisson(6)):
        t = rng.integers(0, n); gaps[t:t + rng.integers(1, 6)] = True
    w.loc[gaps, ["heart_rate_bpm", "resp_rate_bpm", "spo2_pct", "steps", "sleep_hours"]] = np.nan

    ev = pd.DataFrame([{
        "patient_id": p.patient_id, "city": p.city, "onset_date": pd.Timestamp(dates[t0]), "duration_days": dur,
        "prodrome_days": pro, "silent": int(silent),
        "pm25_multiplier": round(float(env_city.m_pm25.values[t0] ** p.pollution_sensitivity), 3),
        "cold_multiplier": round(float(env_city.m_cold.values[t0]), 3),
        "adherence_7d": round(float(adh7[t0]), 2),
    } for t0, dur, pro, silent, size in onsets])
    return w, ev


def build_wearables(seed=SEED):
    rng = np.random.default_rng(seed)
    patients = pd.read_csv(PROCESSED / "patients.csv")
    env = env_multipliers(pd.read_csv(PROCESSED / "environment_daily.csv", parse_dates=["date"]))
    # normalise so the average environmental multiplier across India is 1: annual rates then match ECLIPSE on average
    env["norm"] = (env.m_pm25 * env.m_cold * env.m_humid).mean()
    by_city = {c: d.reset_index(drop=True) for c, d in env.groupby("city")}
    ws, evs = [], []
    # rescale so the record factors shift risk between patients without changing each stage's average rate
    rec = patients.apply(record_multiplier, axis=1)
    rec_norm = rec.groupby(patients.gold_stage).transform("mean")
    for p, rn in zip(patients.itertuples(index=False), rec_norm):
        w, e = simulate_patient(p, by_city[p.city], rng, rn)
        ws.append(w); evs.append(e)
    w = pd.concat(ws, ignore_index=True)
    ev = pd.concat(evs, ignore_index=True)
    w.to_csv(PROCESSED / "wearables_daily.csv", index=False)
    ev.to_csv(PROCESSED / "exacerbation_events.csv", index=False)
    env.drop(columns="norm").to_csv(PROCESSED / "environment_daily.csv", index=False)
    return w, ev


if __name__ == "__main__":
    w, ev = build_wearables()
    p = pd.read_csv(PROCESSED / "patients.csv")
    print(f"{len(w):,} patient-days, {len(ev)} flare-ups across {ev.patient_id.nunique()} of {len(p)} patients")
    rate = ev.merge(p[["patient_id", "gold_stage"]]).groupby("gold_stage").size() / p.groupby("gold_stage").size()
    print("flare-ups per patient-year by stage:", rate.round(2).to_dict())
    print("by city:", (ev.groupby("city").size() / p.groupby("city").size()).round(2).to_dict())
