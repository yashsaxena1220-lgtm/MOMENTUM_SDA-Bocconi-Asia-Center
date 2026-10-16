"""Score every patient-day once so the dashboard opens fast. Output: data/processed/daily_risk.csv"""
import pandas as pd

from config import PROCESSED
from features import build_feature_table
from engine import predict, load as load_model


def main():
    model, meta = load_model()
    w = pd.read_csv(PROCESSED / "wearables_daily.csv", parse_dates=["date"])
    p = pd.read_csv(PROCESSED / "patients.csv")
    env = pd.read_csv(PROCESSED / "environment_daily.csv", parse_dates=["date"])
    f = build_feature_table(w, p, env)
    f["risk"] = predict(f).round(4)
    thr = meta["alert_threshold"]
    f["level"] = pd.cut(f.risk, [-1, thr * 0.5, thr, 2], labels=["Low", "Medium", "High"]).astype(str)
    f.loc[f.in_exacerbation == 1, "level"] = "In flare-up"
    f[["patient_id", "date", "city", "risk", "level", "in_exacerbation", "exacerbation_onset"]].to_csv(
        PROCESSED / "daily_risk.csv", index=False)
    print(f.level.value_counts(normalize=True).round(3).to_dict())


if __name__ == "__main__":
    main()
