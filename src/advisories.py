"""
"Smog is coming" warnings: turn the next few days of air quality and weather into plain advice.

In this demo the dashboard replays 2019-20, so the "forecast" is the real recorded air and weather for
the next days of that year. A live version would read an air-quality forecast instead (for example
SAFAR / CPCB AQI forecasts or the Open-Meteo air-quality forecast) and use exactly the same rules.

Bands are India's CPCB PM2.5 categories (24-hour average, µg/m³). The advice follows common public-health
guidance for people with lung disease; it is general advice, not a prescription.
"""
import pandas as pd

from engine import pm_multiplier

BAD_AIR = ["Poor", "Very Poor", "Severe"]
LEVEL_RANK = {"Good": 0, "Satisfactory": 1, "Moderate": 2, "Poor": 3, "Very Poor": 4, "Severe": 5}

AIR_ADVICE = {
    "Poor": ["Avoid long walks or exercise outdoors, especially early morning and evening",
             "Keep the rescue inhaler with you",
             "Take the daily inhaler every day, without missing doses"],
    "Very Poor": ["Stay indoors as much as possible and keep windows closed",
                  "Wear an N95 mask if you must go out",
                  "Keep the rescue inhaler with you and take the daily inhaler without missing doses",
                  "Avoid other smoke at home: incense, mosquito coils, wood or kerosene cooking"],
    "Severe": ["Stay indoors with windows closed; run an air purifier if you have one",
               "Wear an N95 mask if you must go out, and keep trips short",
               "Keep the rescue inhaler with you and take the daily inhaler without missing doses",
               "Avoid other smoke at home: incense, mosquito coils, wood or kerosene cooking",
               "Call the doctor early if breathing gets worse than usual"],
}
COLD_ADVICE = ["Keep warm at night, especially the chest, and cover the nose and mouth when outside in the cold",
               "Avoid going out early in the morning when it is coldest"]
SEEK_CARE = ("Get medical help straight away if breathing is much worse than usual, lips turn bluish, "
             "speaking is hard, or oxygen (SpO2) falls below 88%.")


def extra_risk_pct(pm25):
    """Extra flare-up risk from this level of PM2.5 compared with clean air (published effect, DeVries 2017)."""
    return float(pm_multiplier([pm25])[0] - 1) * 100


def outlook(env, city, day, days=3):
    """Air and weather for the next `days` days in one city, with warnings."""
    e = env[env.city == city].set_index("date").sort_index()
    today = e.loc[day]
    rows = []
    for d in pd.date_range(day + pd.Timedelta(days=1), periods=days):
        if d not in e.index:
            continue
        r = e.loc[d]
        cold = (today.temp_min_c - r.temp_min_c >= 4) or r.temp_min_c <= 8
        rows.append({"date": d, "pm25": float(r.pm25), "category": r.pm25_category,
                     "temp_min_c": float(r.temp_min_c), "bad_air": r.pm25_category in BAD_AIR, "cold": bool(cold)})
    return rows


def summarise(city, rows):
    """One headline, the worst air category, and a de-duplicated advice list for a city's outlook."""
    if not rows:
        return None
    worst = max(rows, key=lambda r: (LEVEL_RANK.get(r["category"], 0), r["pm25"]))
    bad = [r for r in rows if r["bad_air"]]
    cold = [r for r in rows if r["cold"]]
    if not bad and not cold:
        return {"level": "ok", "worst": worst, "headline": f"{city}: no smog or cold snap expected in the next {len(rows)} days.",
                "advice": [], "extra_risk": 0.0}
    parts = []
    if bad:
        day_names = ", ".join(f"{r['date']:%A}" for r in bad)
        parts.append(f"air expected to be {worst['category'].lower()} on {day_names} "
                     f"(PM2.5 up to {max(r['pm25'] for r in bad):.0f} µg/m³)")
    if cold:
        coldest = min(cold, key=lambda r: r["temp_min_c"])
        parts.append(f"cold night on {coldest['date']:%A} ({coldest['temp_min_c']:.0f}°C)")
    advice = list(AIR_ADVICE.get(worst["category"], [])) if bad else []
    if cold:
        advice += COLD_ADVICE
    level = "severe" if worst["category"] in ("Very Poor", "Severe") else "warning"
    return {"level": level, "worst": worst, "headline": f"{city}: " + " and ".join(parts) + ".",
            "advice": advice, "extra_risk": extra_risk_pct(max((r["pm25"] for r in bad), default=0))}


def all_cities(env, day, cities, days=3):
    out = {c: summarise(c, outlook(env, c, day, days)) for c in cities}
    order = {"severe": 0, "warning": 1, "ok": 2}
    return dict(sorted(((c, s) for c, s in out.items() if s), key=lambda kv: (order[kv[1]["level"]], -kv[1]["worst"]["pm25"])))
