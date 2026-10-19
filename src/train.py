"""
Train the flare-up risk model: "will a COPD flare-up start in the next 1-3 days?"

- Patients are split 70/30, so the model is tested on people it has never seen.
- We also train single-stream models to show what fusing the streams adds.
- Results go to outputs/metrics.json and outputs/*.png for the README and deck.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from sklearn.model_selection import GroupShuffleSplit

from config import PROCESSED, MODELS, OUTPUTS, SEED
from features import build_feature_table, FEATURE_GROUPS, STREAM_OF_GROUP
from twin import URGENT_SPO2
from engine import ml_features, pm_multiplier, combine, PM_COLS

PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_child_samples=80,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0,
              verbose=-1, seed=SEED)
ROUNDS = 400


def load_table():
    w = pd.read_csv(PROCESSED / "wearables_daily.csv", parse_dates=["date"])
    p = pd.read_csv(PROCESSED / "patients.csv")
    env = pd.read_csv(PROCESSED / "environment_daily.csv", parse_dates=["date"])
    f = build_feature_table(w, p, env)
    first = f.groupby("patient_id").date.transform("min")
    keep = (f.in_exacerbation == 0) & (f.date >= first + pd.Timedelta(days=28))   # need history; skip days already ill
    return f[keep].reset_index(drop=True)


# Direction rules so what-if answers make sense: warning signs, sharper cold or sicker records never lower risk;
# taking more inhaler doses never raises it. (PM2.5 enters through the published dose-response in engine.py.)
MONOTONE = {"temp_drop_21d": 1, "adherence_7d": -1, "exacerbations_prior_year": 1, "gold_stage": 1,
            "rr_dev1": 1, "rr_dev3": 1, "rr_z3": 1, "hr_dev1": 1, "hr_dev3": 1, "hr_z3": 1,
            "spo2_dev1": -1, "spo2_dev3": -1, "spo2_z3": -1, "rescue_3d_vs_normal": 1,
            "steps_dev3": -1, "steps_z3": -1,
            "blood_eosinophils_per_ul": 1, "smoker_current": 1, "biomass_fuel_exposure": 1, "comorbidity_count": 1, "age": 1}


def fit(df, feats):
    params = dict(PARAMS, monotone_constraints=[MONOTONE.get(f, 0) for f in feats])
    return lgb.train(params, lgb.Dataset(df[feats], df.onset_within_3d), ROUNDS)


def event_level(test, prob, thr):
    """Share of flare-ups preceded by an alert in the 3 days before onset, and false alerts per patient-month."""
    # safety layer: oxygen below 90% always raises an alert, whatever the model's probability (see twin.final_level)
    t = test.assign(alert=(prob >= thr) | (test.spo2_pct < URGENT_SPO2))
    caught = t[t.onset_within_3d == 1].groupby(["patient_id", "event_key"]).alert.any()
    false_alerts = (t.alert & (t.onset_within_3d == 0)).sum()
    patient_months = len(t) / 30.4
    return float(caught.mean()), float(false_alerts / patient_months)


def main():
    df = load_table()
    # tag each 3-day pre-onset window with an event key so detection is counted per flare-up
    df["event_key"] = (df.onset_within_3d.diff().fillna(df.onset_within_3d) == 1).groupby(df.patient_id).cumsum()
    feats = ml_features()
    tr_idx, te_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=SEED).split(df, groups=df.patient_id))
    train, test = df.iloc[tr_idx], df.iloc[te_idx]
    pm_norm = float(pm_multiplier(train.pm25_lag2_7).mean())

    model = fit(train, feats)
    prob = combine(model.predict(test[feats]), test.pm25_lag2_7, pm_norm)
    # alert threshold: chosen on TRAINING patients to give about 1 alert per patient-month
    p_train = combine(model.predict(train[feats]), train.pm25_lag2_7, pm_norm)
    thr = float(np.quantile(p_train, 1 - 1 / 30.4))
    sens, fa = event_level(test, prob, thr)

    streams = {"wearable": [], "environment": [], "ehr": []}
    for grp, cols in FEATURE_GROUPS.items():
        streams[STREAM_OF_GROUP[grp]] += cols
    ablation = {}
    env_ml = [c for c in streams["environment"] if c not in PM_COLS]
    for name, cols, use_pm in [("Health record only", streams["ehr"], False),
                               ("Environment only", env_ml, True),
                               ("Wearables only", streams["wearable"], False),
                               ("Wearables + health record", streams["wearable"] + streams["ehr"], False),
                               ("All three streams (twin)", feats, True)]:
        m = model if name.startswith("All") else fit(train, cols)
        pr = m.predict(test[cols])
        if use_pm:
            pr = combine(pr, test.pm25_lag2_7, pm_norm)
        ablation[name] = {"auroc": round(roc_auc_score(test.onset_within_3d, pr), 3),
                          "auprc": round(average_precision_score(test.onset_within_3d, pr), 3)}

    contrib = model.predict(test[feats], pred_contrib=True)[:, :-1]
    imp = pd.Series(np.abs(contrib).mean(0), index=feats)
    group_imp = {g: float(imp[[c for c in cols if c in feats]].sum()) for g, cols in FEATURE_GROUPS.items()}
    group_imp["Air pollution (PM2.5)"] = float(np.abs(np.log(pm_multiplier(test.pm25_lag2_7) / pm_norm)).mean())
    total = sum(group_imp.values())
    group_imp = {g: round(v / total * 100, 1) for g, v in sorted(group_imp.items(), key=lambda kv: -kv[1])}

    metrics = {
        "task": "Predict whether a COPD flare-up starts in the next 1-3 days",
        "patients_train": int(train.patient_id.nunique()), "patients_test": int(test.patient_id.nunique()),
        "patient_days_test": int(len(test)), "positive_rate_test": round(float(test.onset_within_3d.mean()), 4),
        "auroc": round(roc_auc_score(test.onset_within_3d, prob), 3),
        "auprc": round(average_precision_score(test.onset_within_3d, prob), 3),
        "alert_threshold": round(thr, 4),
        "flare_ups_warned_in_advance": round(sens, 3),
        "false_alerts_per_patient_month": round(fa, 2),
        "single_stream_ablation": ablation,
        "trigger_group_importance_pct": group_imp,
        "pm25_method": "Published dose-response (DeVries 2017) applied on the odds scale; not learned by the model.",
        "published_benchmark": "Real-world studies report AUROC 0.68 (Shah 2017) to 0.85 (Hurst 2010).",
        "caveat": "Measured on simulated data; reflects the simulator's assumptions, not clinical accuracy.",
    }
    MODELS.mkdir(exist_ok=True); OUTPUTS.mkdir(exist_ok=True)
    model.save_model(str(MODELS / "flare_risk_lgbm.txt"))
    json.dump({"features": feats, "alert_threshold": thr, "pm_norm": pm_norm, "groups": FEATURE_GROUPS}, open(MODELS / "model_meta.json", "w"), indent=2)
    json.dump(metrics, open(OUTPUTS / "metrics.json", "w"), indent=2)

    fpr, tpr, _ = roc_curve(test.onset_within_3d, prob)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].plot(fpr, tpr, color="#1f6f8b", lw=2, label=f"Twin model (AUROC {metrics['auroc']})")
    ax[0].plot([0, 1], [0, 1], ls="--", color="#999", lw=1)
    ax[0].set(xlabel="False positive rate", ylabel="True positive rate", title="Flare-up in next 3 days: held-out patients")
    ax[0].legend(loc="lower right", frameon=False)
    names = list(ablation)[::-1]
    ax[1].barh(names, [ablation[n]["auroc"] for n in names], color=["#1f6f8b"] + ["#9fb7c2"] * (len(names) - 1))
    ax[1].set_xlim(0.5, 1); ax[1].set(xlabel="AUROC", title="What fusing the streams adds")
    for i, n in enumerate(names):
        ax[1].text(ablation[n]["auroc"] + 0.005, i, f"{ablation[n]['auroc']:.2f}", va="center", fontsize=9)
    for a in ax: a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUTPUTS / "model_performance.png", dpi=160)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    gi = pd.Series(group_imp)[::-1]
    ax.barh(gi.index, gi.values, color="#1f6f8b")
    ax.set(xlabel="Share of model's reasoning (%)", title="Which triggers drive flare-up risk")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUTPUTS / "trigger_importance.png", dpi=160)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
