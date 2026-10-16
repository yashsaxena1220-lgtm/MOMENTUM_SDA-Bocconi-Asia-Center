"""
Environment stream: real daily air quality (CPCB, via Kaggle city_day.csv) and real
daily weather (Open-Meteo historical archive) for the training cities.

Inputs  (data/raw/):  city_day.csv, weather_8cities.csv
Output  (data/processed/): environment_daily.csv
"""
import io
import numpy as np
import pandas as pd

from config import RAW, PROCESSED, CITIES, START_DATE, END_DATE


def load_air_quality(path=RAW / "city_day.csv"):
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df[df.City.isin(CITIES) & df.Date.between(START_DATE, END_DATE)]
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    out = []
    for city in CITIES:
        c = df[df.City == city].set_index("Date").reindex(dates)
        pm = c["PM2.5"].astype(float)
        imputed = pm.isna()
        pm = pm.interpolate(limit=10, limit_direction="both")
        # longer gaps: that month's median for the city
        month_med = pm.groupby(pm.index.month).transform("median")
        pm = pm.fillna(month_med)
        out.append(pd.DataFrame({
            "city": city, "date": dates, "pm25": pm.round(1).values,
            "aqi": c["AQI"].astype(float).values, "aqi_bucket": c["AQI_Bucket"].values,
            "pm25_imputed": imputed.astype(int).values,
        }))
    return pd.concat(out, ignore_index=True)


def load_weather(path=RAW / "weather_8cities.csv"):
    """Parse Open-Meteo's multi-location CSV (metadata block, blank line, data block)."""
    text = path.read_text(encoding="utf-8-sig")
    start = text.index("location_id,time")
    df = pd.read_csv(io.StringIO(text[start:]))
    df.columns = [c.split(" (")[0] for c in df.columns]
    city_by_id = dict(enumerate(CITIES))          # request order = CITIES order (see README)
    df["city"] = df.location_id.map(city_by_id)
    df["date"] = pd.to_datetime(df.time)
    return df.rename(columns={"temperature_2m_mean": "temp_mean_c",
                              "temperature_2m_min": "temp_min_c",
                              "relative_humidity_2m_mean": "humidity_pct"})[
        ["city", "date", "temp_mean_c", "temp_min_c", "humidity_pct"]]


def build_environment():
    env = load_air_quality().merge(load_weather(), on=["city", "date"], how="left")
    env = env.sort_values(["city", "date"]).reset_index(drop=True)
    g = env.groupby("city")
    env["temp_change_c"] = g.temp_mean_c.diff().fillna(0).round(1)       # day-to-day change
    env["pm25_7d"] = g.pm25.transform(lambda s: s.rolling(7, min_periods=1).mean()).round(1)
    # India National AQI category from 24-h PM2.5 (where the source AQI bucket is missing)
    bins = [0, 30, 60, 90, 120, 250, np.inf]
    labels = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    env["pm25_category"] = pd.cut(env.pm25, bins=bins, labels=labels, include_lowest=True).astype(str)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    env.to_csv(PROCESSED / "environment_daily.csv", index=False)
    return env


if __name__ == "__main__":
    e = build_environment()
    print(e.groupby("city").agg(pm25_mean=("pm25", "mean"), pm25_max=("pm25", "max"),
                                imputed_days=("pm25_imputed", "sum"), temp_min=("temp_min_c", "min"),
                                humidity=("humidity_pct", "mean")).round(1))
