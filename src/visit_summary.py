"""
One-page visit summary a patient or family can print (or save as PDF from the browser) and take to the doctor.

Built as a self-contained HTML page: the last 30 days of readings against the patient's own normal,
inhaler use, flare-ups, the twin's alerts, air quality, and questions worth asking.
"""
import base64
import html
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from advisories import SEEK_CARE

INK, TEAL, RED, PURPLE, BAND = "#1B2A35", "#1F5F7A", "#B23A2E", "#6B4E71", "#DCE9EF"
LEVEL_COLOR = {"Low": "#5B8A72", "Medium": "#C98A1B", "High": RED, "In flare-up": PURPLE}
COMORB = {"hypertension": "high blood pressure", "diabetes": "diabetes", "ischemic_heart_disease": "heart disease",
          "heart_failure": "heart failure", "anemia": "anaemia"}


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _charts(h, thr, flare_days):
    panels = [("resp_rate_bpm", "rr_normal", "Breathing rate (breaths/min)", 1.2),
              ("spo2_pct", "spo2_normal", "Blood oxygen, SpO2 (%)", 1.0),
              ("heart_rate_bpm", "hr_normal", "Resting heart rate (bpm)", 4.9),
              ("steps", "steps_normal", "Steps per day", 1200)]
    fig, axes = plt.subplots(5, 1, figsize=(7.2, 7.4), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1, 1, 1.1]})
    for ax, (col, norm, title, sd) in zip(axes, panels):
        ax.fill_between(h.date, h[norm] - sd, h[norm] + sd, color=BAND, lw=0, label="own normal range")
        ax.plot(h.date, h[col], color=INK, lw=1.3, marker="o", ms=2.5)
        ax.set_title(title, loc="left", fontsize=8.5, color=INK, pad=2)
    ax = axes[-1]
    ax.fill_between(h.date, 0, h.risk * 100, color=TEAL, alpha=0.18, lw=0)
    ax.plot(h.date, h.risk * 100, color=TEAL, lw=1.6)
    ax.axhline(thr * 100, color=RED, ls=":", lw=1)
    ax.text(h.date.iloc[0], thr * 100, " alert line", color=RED, fontsize=7, va="bottom")
    ax.set_title("Twin's flare-up risk, next 3 days (%)", loc="left", fontsize=8.5, color=INK, pad=2)
    for a in axes:
        for d in flare_days:
            a.axvspan(d - pd.Timedelta(hours=12), d + pd.Timedelta(hours=12), color=PURPLE, alpha=0.18, lw=0)
        a.spines[["top", "right"]].set_visible(False)
        a.tick_params(labelsize=7)
    axes[-1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    fig.tight_layout(h_pad=0.6)
    return _png(fig)


def _fmt(v, f=".1f"):
    return "–" if v is None or pd.isna(v) else format(v, f)


def build_summary_html(p, a, hist, env_city, day, thr, outlook=None, days=30):
    """p: patient record row; a: twin.assess() result for `day`; hist: score_history() rows up to `day`."""
    h = hist[hist.date > day - pd.Timedelta(days=days)].copy()
    e = env_city[env_city.date.between(h.date.min(), day)]
    flare_days = list(h.date[h.in_exacerbation == 1]) if "in_exacerbation" in h else []
    onsets = list(h.date[h.exacerbation_onset == 1]) if "exacerbation_onset" in h else []
    high_days = h[(h.risk >= thr) & (h.get("in_exacerbation", 0) == 0)]
    warned = [d for d in onsets if ((high_days.date >= d - pd.Timedelta(days=3)) & (high_days.date < d)).any()]
    last3 = h.tail(3)

    rows = []
    for name, col, norm, unit, f in [("Breathing rate", "resp_rate_bpm", "rr_normal", "breaths/min", ".1f"),
                                     ("Blood oxygen (SpO2)", "spo2_pct", "spo2_normal", "%", ".1f"),
                                     ("Resting heart rate", "heart_rate_bpm", "hr_normal", "bpm", ".0f"),
                                     ("Steps", "steps", "steps_normal", "per day", ".0f"),
                                     ("Sleep", "sleep_hours", "sleep_normal", "hours", ".1f")]:
        rows.append(f"<tr><td>{name}</td><td>{unit}</td><td>{_fmt(h[norm].iloc[-1], f)}</td><td>{_fmt(h[col].mean(), f)}</td>"
                    f"<td><b>{_fmt(last3[col].mean(), f)}</b></td><td>{_fmt(h[col].min(), f)} – {_fmt(h[col].max(), f)}</td></tr>")
    worn = h.heart_rate_bpm.notna().mean()

    prescribed = float(h.controller_doses_prescribed.max()) if "controller_doses_prescribed" in h else 0
    if prescribed:
        taken = h.controller_doses_taken.sum() / (prescribed * len(h))
        missed_days = int((h.controller_doses_taken < prescribed).sum())
        inhaler = f"Daily inhaler: <b>{taken:.0%}</b> of prescribed doses taken; doses missed on {missed_days} of {len(h)} days."
    else:
        taken, inhaler = 1.0, "No daily (controller) inhaler prescribed."
    rescue_now, rescue_avg = last3.rescue_puffs.mean(), h.rescue_puffs.mean()
    inhaler += f" Rescue inhaler: {rescue_avg:.1f} puffs/day on average, {rescue_now:.1f} in the last 3 days."

    bad_air = int(e.pm25_category.isin(["Poor", "Very Poor", "Severe"]).sum())
    air = (f"Average PM2.5 {e.pm25.mean():.0f} µg/m³ (safe level 15, India's limit 60). {bad_air} of {len(e)} days were poor or worse. "
           f"Coldest night {e.temp_min_c.min():.0f}°C.")

    record = [f"GOLD {int(p.gold_stage)}", f"{int(p.exacerbations_prior_year)} flare-up{'' if p.exacerbations_prior_year == 1 else 's'} in the year before monitoring",
              f"smoking: {p.smoking_status}", f"cooking smoke at home: {'yes' if p.biomass_fuel_exposure else 'no'}",
              f"blood eosinophils {int(p.blood_eosinophils_per_ul)} cells/µL", f"BMI {p.bmi:.1f}" if pd.notna(p.bmi) else "",
              f"flu vaccine this year: {'yes' if p.influenza_vaccinated else 'no'}",
              "on home oxygen" if p.home_oxygen else ""]
    others = [v for k, v in COMORB.items() if getattr(p, k, 0)]
    if others:
        record.append("other conditions: " + ", ".join(others))

    questions = []
    if prescribed and taken < 0.8:
        questions.append("Doses are often missed. Is the inhaler hard to use, too costly, or causing side effects?")
    if (a["row"].get("rescue_3d_vs_normal", 0) or 0) >= 1:
        questions.append("The rescue inhaler is being used more than usual. Does the treatment need changing?")
    if a["level"] in ("High", "Medium"):
        questions.append("The twin flags a raised flare-up risk. Should we start the written action plan (for example a standby course of medicine)?")
    if not p.influenza_vaccinated:
        questions.append("Should the patient get this year's flu vaccine (and a pneumonia vaccine)?")
    if p.smoking_status == "current":
        questions.append("What help is available to stop smoking, including bidis?")
    if p.biomass_fuel_exposure:
        questions.append("How can we cut smoke from cooking at home (LPG, ventilation, chimney)?")
    if bad_air:
        questions.append("What should we do on high-pollution days?")
    if p.blood_eosinophils_per_ul >= 300:
        questions.append("Eosinophils are high. Would an inhaled steroid help prevent flare-ups?")
    questions.append("Is the inhaler technique correct? (Please check it during the visit.)")

    triggers = "".join(f"<li>{html.escape(t['text'])}</li>" for t in a["triggers"]) or "<li>No single factor stands out.</li>"
    rules = "".join(f"<li>{html.escape(t)}</li>" for _, t in a["rules"]) or (
        "<li>No single reading has crossed a warning line yet, but several smaller changes together raise the risk.</li>"
        if a["level"] in ("High", "Medium") else "<li>All readings within own normal range.</li>")
    flare_txt = (f"{len(onsets)} flare-up(s) started in this period ({', '.join(f'{d:%d %b}' for d in onsets)}). "
                 f"The twin raised an alert 1-3 days before {len(warned)} of them." if onsets else "No flare-up started in this period.")
    alerts_txt = f"The twin flagged high risk on {len(high_days)} of {len(h)} days."
    out_txt = ""
    if outlook and outlook["level"] != "ok":
        out_txt = (f"<h2>Next few days</h2><p>{html.escape(outlook['headline'])}</p><ul>"
                   + "".join(f"<li>{html.escape(x)}</li>" for x in outlook["advice"]) + "</ul>")
    col = LEVEL_COLOR.get(a["level"], TEAL)
    chart = _charts(h, thr, flare_days)

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Visit summary - {html.escape(str(p.display_name))} - {day:%d %b %Y}</title>
<style>
 @page {{ size: A4; margin: 12mm; }}
 body {{ font-family: Arial, Helvetica, sans-serif; color: {INK}; font-size: 11px; line-height: 1.35; max-width: 780px; margin: 16px auto; }}
 h1 {{ font-size: 18px; margin: 0; }} h2 {{ font-size: 12.5px; margin: 10px 0 4px; color: {TEAL}; border-bottom: 1px solid #D6E0E7; padding-bottom: 2px; }}
 .top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
 .muted {{ color: #536673; }} .risk {{ border: 2px solid {col}; border-radius: 8px; padding: 6px 10px; text-align: center; min-width: 150px; }}
 .risk .v {{ font-size: 24px; font-weight: bold; color: {col}; }}
 .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
 table {{ border-collapse: collapse; width: 100%; }} td, th {{ border-bottom: 1px solid #E4EBF0; padding: 3px 4px; text-align: left; }}
 th {{ background: #F3F6F8; font-weight: bold; }} ul {{ margin: 2px 0; padding-left: 16px; }}
 .care {{ background: #F3DEDB; border-radius: 6px; padding: 6px 8px; margin-top: 8px; }}
 img {{ width: 100%; }} .foot {{ font-size: 9px; color: #536673; margin-top: 8px; }}
 @media print {{ .noprint {{ display: none; }} body {{ margin: 0; }} }}
</style></head><body>
<p class="noprint muted">To save as PDF: press Ctrl+P and choose "Save as PDF".</p>
<div class="top"><div>
<h1>Visit summary: {html.escape(str(p.display_name))}</h1>
<div class="muted">{int(p.age)} yrs · {'Male' if p.sex == 'M' else 'Female'} · {html.escape(str(p.city))} · COPD ({html.escape(str(p.copd_type)).lower()})<br>
Period: {h.date.min():%d %b %Y} to {day:%d %b %Y} ({len(h)} days) · Watch worn on {worn:.0%} of days</div>
<div style="margin-top:4px">{' · '.join(html.escape(x) for x in record if x)}</div>
</div><div class="risk"><div class="muted">Flare-up risk, next 3 days</div><div class="v">{a['prob']:.1%}</div><b style="color:{col}">{a['level']} risk</b></div></div>

<div class="cols"><div>
<h2>Why the twin thinks so</h2><ul>{triggers}</ul>
<h2>Checks against own normal</h2><ul>{rules}</ul>
</div><div>
<h2>Flare-ups and alerts</h2><p>{flare_txt} {alerts_txt}</p>
<h2>Inhalers</h2><p>{inhaler}</p>
<h2>Air and weather</h2><p>{air}</p>
</div></div>

<h2>Readings: own normal vs last 30 days</h2>
<table><tr><th>Reading</th><th>Unit</th><th>Own normal</th><th>30-day average</th><th>Last 3 days</th><th>Range</th></tr>{''.join(rows)}</table>

<h2>Last 30 days at a glance</h2>
<img src="data:image/png;base64,{chart}" alt="Daily readings against own normal, and flare-up risk">
<div class="muted">Shaded band: this person's normal range. Purple shading: days in a flare-up. Gaps: watch not worn. Dotted red line: alert line.</div>

<div class="cols"><div>{out_txt}</div><div>
<h2>Questions to ask the doctor</h2><ul>{''.join(f'<li>{html.escape(q)}</li>' for q in questions[:6])}</ul>
</div></div>
<div class="care"><b>When to get help now:</b> {SEEK_CARE}</div>
<div class="foot">Made by BreatheTwin (Team MOMENTUM) on {day:%d %b %Y}. This summary supports, and does not replace, the doctor's judgement.
In this prototype the patient, watch readings and flare-ups are simulated; air quality (CPCB) and weather (Open-Meteo) are real.</div>
</body></html>"""
