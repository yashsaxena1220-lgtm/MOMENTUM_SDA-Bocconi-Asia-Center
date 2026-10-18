"""
BreatheTwin: COPD digital twin, doctor dashboard.

Run:  python -m streamlit run app/dashboard.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import PROCESSED, OUTPUTS, CITIES, CALIBRATION, START_DATE, END_DATE, SEED, cal  # noqa: E402
from twin import assess, score_history, score_row, sweep, rule_checks, risk_level, threshold, trigger_text  # noqa: E402
from simulate import env_multipliers, simulate_patient  # noqa: E402
from engine import load as load_engine  # noqa: E402
from advisories import all_cities, summarise, outlook, SEEK_CARE  # noqa: E402
from visit_summary import build_summary_html  # noqa: E402
from devices import SIGNALS, DEVICES, KITS  # noqa: E402

st.set_page_config(page_title="BreatheTwin | COPD digital twin", page_icon="🫁", layout="wide",
                   initial_sidebar_state="expanded")

NAVY, TEAL, INK, MIST, LINE = "#12303F", "#1F5F7A", "#1B2A35", "#E4EBF0", "#D6E0E7"
RISK = {"High": "#B23A2E", "Medium": "#C98A1B", "Low": "#5B8A72", "In flare-up": "#6B4E71"}
UP, DOWN, SMOG = "#B23A2E", "#3C7A5E", "#8C7B55"
AQI_SCALE = [[0, "#5B8A72"], [0.12, "#9BB45A"], [0.24, "#D9B83F"], [0.36, "#D9883F"], [0.5, "#B23A2E"], [1, "#5E1F3A"]]

st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,650&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"], .stMarkdown, button, input, select, textarea, label {{ font-family: 'Atkinson Hyperlegible', sans-serif; }}
h1, h2, h3 {{ font-family: 'Source Serif 4', Georgia, serif !important; color: {INK}; letter-spacing: -0.01em; }}
h3 {{ font-size: 1.25rem !important; margin-top: 0.6rem !important; }}
.block-container {{ padding-top: 1.2rem; max-width: 1400px; }}
.band {{ background: {NAVY}; color: #fff; border-radius: 14px; padding: 1.1rem 1.4rem; margin-bottom: 1rem;
         display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; }}
.band h1 {{ color: #fff !important; margin: 0 !important; font-size: 1.9rem !important; line-height: 1.15 !important; }}
.band .sub {{ color: #B9CCD8; font-size: 0.95rem; margin-top: 0.25rem; }}
.chip {{ display: inline-block; padding: 0.15rem 0.65rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; color: #fff; }}
.chip.live {{ background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.35); }}
.kpi {{ background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 0.8rem 1rem; height: 100%; }}
.kpi .v {{ font-family: 'Source Serif 4', serif; font-size: 2rem; line-height: 1.1; color: {INK}; }}
.kpi .l {{ color: #536673; font-size: 0.88rem; }}
.kpi .d {{ font-size: 0.85rem; margin-top: 0.15rem; }}
.card {{ background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 0.9rem 1rem; margin-bottom: 0.7rem; }}
.alert {{ display: grid; grid-template-columns: 4.2rem 1fr; gap: 0.7rem; align-items: center; background: #fff;
          border: 1px solid {LINE}; border-left-width: 5px; border-radius: 10px; padding: 0.55rem 0.8rem; margin-bottom: 0.45rem; }}
.alert .pct {{ font-family: 'Source Serif 4', serif; font-size: 1.45rem; text-align: right; }}
.alert .who {{ font-weight: 700; }}
.alert .why {{ color: #536673; font-size: 0.88rem; }}
.rule {{ border-left: 4px solid; padding: 0.4rem 0.75rem; margin: 0.3rem 0; background: #fff; border-radius: 0 8px 8px 0; }}
.muted {{ color: #536673; font-size: 0.9rem; }}
.vital {{ background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 0.7rem 0.9rem; }}
.vital .n {{ color: #536673; font-size: 0.85rem; }}
.vital .x {{ font-family: 'Source Serif 4', serif; font-size: 1.7rem; }}
div[data-testid="stSidebar"] {{ background: #E7EEF2; }}
.howto {{ background: #EAF3F6; border: 1px solid #C9DEE6; border-radius: 12px; padding: 0.75rem 1rem; margin-bottom: 1rem; }}
.howto b.h {{ color: {TEAL}; }}
.howto ul {{ margin: 0.3rem 0 0 0; padding-left: 1.2rem; }}
.howto li {{ margin-bottom: 0.15rem; }}
.legend span {{ display: inline-block; margin-right: 0.4rem; }}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_data
def load_all():
    p = pd.read_csv(PROCESSED / "patients.csv")
    w = pd.read_csv(PROCESSED / "wearables_daily.csv", parse_dates=["date"])
    env = pd.read_csv(PROCESSED / "environment_daily.csv", parse_dates=["date"])
    risk = pd.read_csv(PROCESSED / "daily_risk.csv", parse_dates=["date"])
    ev = pd.read_csv(PROCESSED / "exacerbation_events.csv", parse_dates=["onset_date"])
    return p, w, env, risk, ev


patients, wear, env, risk, events = load_all()
THR = threshold()
P = patients.set_index("patient_id")


@st.cache_data(show_spinner=False)
def assess_cached(pid, day):
    p_row = patients[patients.patient_id == pid].iloc[0]
    a = assess(p_row, wear[(wear.patient_id == pid) & (wear.date <= day)], env[env.city == p_row.city])
    return {k: v for k, v in a.items()}


@st.cache_data(show_spinner=False)
def history_cached(pid, day):
    p_row = patients[patients.patient_id == pid].iloc[0]
    return score_history(p_row, wear[(wear.patient_id == pid) & (wear.date <= day)], env[env.city == p_row.city])


def chip(level):
    return f'<span class="chip" style="background:{RISK.get(level, TEAL)}">{level}</span>'


def pct(x):
    return f"{x:.1%}" if x < 0.1 else f"{x:.0%}"


def band(title, sub):
    st.markdown(f'<div class="band"><div><h1>{title}</h1><div class="sub">{sub}</div></div>'
                f'<div><span class="chip live">Replaying {day:%d %b %Y}</span></div></div>', unsafe_allow_html=True)


def kpi(col, value, label, delta="", color=INK):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v" style="color:{color}">{value}</div>'
                 f'<div class="d">{delta}</div></div>', unsafe_allow_html=True)


LEVEL_MEANING = {"Low": "No action needed. Keep the usual routine.",
                 "Medium": "Watch closely. Check in with the patient in the next day or two.",
                 "High": "Contact the patient today. A flare-up is likely in the next 3 days.",
                 "In flare-up": "The patient is having a flare-up now."}

GLOSSARY = {
    "COPD": "Chronic obstructive pulmonary disease. A long-term lung disease that makes breathing hard. Common in India because of smoking, cooking smoke and air pollution.",
    "Flare-up": "A sudden worsening of COPD over a few days: more breathlessness, coughing and mucus. Doctors call it an exacerbation. It often needs extra medicine or a hospital visit.",
    "Digital twin": "A computer copy of a patient that is updated every day with their readings, so it can warn early and test 'what if' questions safely.",
    "Risk %": "The chance of a flare-up starting in the next 3 days. 10% means about 1 in 10 people with these readings would have one.",
    "Alert line": "The risk level above which the twin flags a patient as High risk.",
    "Own normal": "What is usual for this person, worked out from their own readings over the past month. Changes from their own normal matter more than textbook ranges.",
    "GOLD stage": "How severe the COPD is, from 1 (mild) to 4 (very severe), based on a breathing test.",
    "SpO2 (blood oxygen)": "How much oxygen the blood carries, measured by a finger clip or smartwatch. Healthy people are 95-100%. COPD patients are often lower; a drop from their usual is a warning sign.",
    "Breathing rate": "Breaths per minute at rest. Usually 12-20. Breathing faster than usual is one of the earliest warning signs.",
    "Rescue inhaler": "The quick-relief inhaler (for example salbutamol) used when breathless. Using it more than usual is a warning sign.",
    "Controller inhaler": "The daily inhaler taken every day to keep COPD stable. Missing doses raises risk.",
    "PM2.5": "Tiny smoke and dust particles in the air, measured in µg/m³ (micrograms per cubic metre). WHO daily safe level is 15, India's limit is 60. Above 250 is severe.",
    "AQI": "Air Quality Index, a 0-500 score shown in apps. It is not the same number as PM2.5.",
    "Eosinophils": "A type of white blood cell from a routine blood test. High levels mean flare-ups are more likely and respond to steroid treatment.",
}


def howto(title, points):
    items = "".join(f"<li>{x}</li>" for x in points)
    st.markdown(f'<div class="howto"><b class="h">{title}</b><ul>{items}</ul></div>', unsafe_allow_html=True)


def base_layout(fig, h, title=None, **kw):
    fig.update_layout(height=h, margin=dict(l=8, r=8, t=36 if title else 8, b=8), plot_bgcolor="white",
                      paper_bgcolor="white", font=dict(family="Atkinson Hyperlegible, sans-serif", color=INK, size=12),
                      title=dict(text=title, font=dict(size=14, family="Source Serif 4, serif")) if title else None, **kw)
    fig.update_xaxes(showgrid=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=MIST, zeroline=False)
    return fig


def gauge(prob, ref=None, h=230, title="Flare-up risk, next 3 days"):
    lv = risk_level(prob)
    top = min(1.0, max(0.6, prob * 1.15))
    fig = go.Figure(go.Indicator(
        mode="gauge+number" + ("+delta" if ref is not None else ""), value=prob * 100,
        number=dict(suffix="%", valueformat=".1f", font=dict(size=40, family="Source Serif 4, serif", color=RISK[lv])),
        delta=dict(reference=ref * 100, valueformat=".1f", suffix=" pts", increasing=dict(color=UP), decreasing=dict(color=DOWN))
        if ref is not None else None,
        gauge=dict(axis=dict(range=[0, top * 100], ticksuffix="%", tickcolor=LINE), bar=dict(color=RISK[lv], thickness=0.28),
                   bgcolor="white", borderwidth=0,
                   steps=[dict(range=[0, THR * 50], color="#E3EEE7"), dict(range=[THR * 50, THR * 100], color="#F5EBD6"),
                          dict(range=[THR * 100, top * 100], color="#F3DEDB")],
                   threshold=dict(line=dict(color=INK, width=2), thickness=0.8, value=THR * 100)),
        title=dict(text=title, font=dict(size=13))))
    return base_layout(fig, h)


def push_chart(groups, h=330):
    s = pd.Series(groups).rename({"Clinical history": "Health record"}).sort_values()
    s = s[s.abs() > 0.01]
    shown = s.clip(-3, 3)                      # very large pushes are drawn at the edge; the label and hover say how big

    def label(v):
        m = np.exp(v)
        if v > 0:
            return "strongly raises risk" if m >= 5 else f"raises risk x{m:.1f}"
        return "strongly lowers risk" if m <= 0.2 else f"lowers risk x{m:.2f}"

    fig = go.Figure(go.Bar(x=shown.values, y=s.index, orientation="h", marker_color=[UP if v > 0 else DOWN for v in s.values],
                           text=[label(v) if abs(v) > 0.15 else "" for v in s.values],
                           textposition="inside", insidetextanchor="middle", textfont=dict(color="white"),
                           hovertemplate="%{y}: odds x%{customdata:.2f}<extra></extra>", customdata=np.exp(s.values)))
    fig.add_vline(x=0, line=dict(color=INK, width=1))
    base_layout(fig, h, "What is pushing the risk up or down")
    fig.update_layout(uniformtext=dict(minsize=10, mode="hide"))
    fig.update_xaxes(title="← lowers risk          raises risk →",
                     range=[min(-0.5, shown.min() * 1.15), max(0.5, shown.max() * 1.15)])
    return fig


RULE_COLORS = {"urgent": "#B23A2E", "warning": "#C98A1B", "watch": "#8C7B55"}
NO_SINGLE_SIGN = ("No single reading has crossed a warning line yet, but several smaller changes together raise the risk. "
                  "See <b>what is pushing the risk</b>.")
VERY_HIGH = 0.6


def show_checks(rules, prob, limit=None):
    """Rule checks; never says 'all normal' while the twin itself flags a raised risk."""
    if rules:
        for kind, text in rules[:limit]:
            st.markdown(f'<div class="rule" style="border-color:{RULE_COLORS[kind]}">{text}</div>', unsafe_allow_html=True)
    elif risk_level(prob) in ("High", "Medium"):
        st.markdown(f'<div class="rule" style="border-color:#C98A1B">{NO_SINGLE_SIGN}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="rule" style="border-color:#5B8A72">All readings within own normal range</div>', unsafe_allow_html=True)


def show_scenarios(prob, scenarios):
    """What would lower the risk; when risk is already very high, say so instead of showing 98% -> 98%."""
    if prob >= VERY_HIGH:
        st.markdown(f'<div class="rule" style="border-color:#B23A2E"><b>Risk is already very high ({pct(prob)}).</b> '
                    "Contact the doctor today. Staying indoors and taking every inhaler dose still help, but they will not "
                    "stop a flare-up that may already be starting.</div>", unsafe_allow_html=True)
        return
    for name, v in scenarios.items():
        ch = (v - prob) / prob if prob > 0 else 0
        st.markdown(f'<div class="rule" style="border-color:{DOWN if ch < -0.05 else LINE}">{name}: '
                    f'<b>{pct(prob)} → {pct(v)}</b> ({ch:+.0%})</div>', unsafe_allow_html=True)


def signal_chart(f, col, normal_col, title, sd):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=f.date, y=f[normal_col] + sd, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f.date, y=f[normal_col] - sd, line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(31,95,122,0.13)", name="Own normal", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f.date, y=f[col], mode="lines+markers", line=dict(color=INK, width=1.6), marker=dict(size=4), name=title))
    return base_layout(fig, 200, title, showlegend=False)


ADV_STYLE = {"severe": ("#B23A2E", "#F8E5E2"), "warning": ("#C98A1B", "#FBF1DD"), "ok": ("#5B8A72", "#E6F0EA")}
FORECAST_NOTE = ("In this demo the 'forecast' is the real recorded air and weather for the next days of 2019-20. "
                 "A live version would use an air-quality forecast service with the same rules.")


def advisory_card(s, show_risk=True):
    edge, bg = ADV_STYLE[s["level"]]
    icon = {"severe": "⚠️", "warning": "⚠️", "ok": "✅"}[s["level"]]
    risk = (f"<div class='muted' style='margin-top:0.3rem'>At this level of PM2.5, a COPD patient's flare-up risk over the following "
            f"week is about <b>{s['extra_risk']:.0f}% higher</b> than on a clean-air day (published effect).</div>"
            if show_risk and s["extra_risk"] >= 5 else "")
    tips = "".join(f"<li>{t}</li>" for t in s["advice"])
    st.markdown(f'<div class="card" style="border-left:5px solid {edge};background:{bg}"><b>{icon} {s["headline"]}</b>' +
                (f'<ul style="margin:0.3rem 0 0 0">{tips}</ul>' if tips else "") + f'{risk}</div>',
                unsafe_allow_html=True)


def record_tags(p):
    """Short health-record facts that matter for flare-up risk, for cards and headers."""
    tags = [f"GOLD {int(p.gold_stage)}"]
    n = int(p.exacerbations_prior_year)
    tags.append(f"{n} flare-up{'' if n == 1 else 's'} last year")
    if p.smoking_status == "current":
        tags.append("smokes" + (f" ({p.tobacco_type})" if p.tobacco_type not in ("none", "") else ""))
    if p.biomass_fuel_exposure:
        tags.append("cooking smoke")
    if p.blood_eosinophils_per_ul >= 300:
        tags.append(f"high eosinophils {int(p.blood_eosinophils_per_ul)}")
    conds = int(sum(p.get(c, 0) for c in ["hypertension", "diabetes", "ischemic_heart_disease", "heart_failure", "anemia"]))
    if conds:
        tags.append(f"{conds} other condition{'' if conds == 1 else 's'}")
    if p.home_oxygen:
        tags.append("home oxygen")
    if not p.influenza_vaccinated:
        tags.append("no flu vaccine")
    return tags


def nearest_city(lat, lon):
    d = {c: (v["lat"] - lat) ** 2 + ((v["lon"] - lon) * np.cos(np.radians(lat))) ** 2 for c, v in CITIES.items()}
    return min(d, key=d.get)


def feed_from_readings(usual, now, doses_7d, prescribed, end_day, city, n_days=45):
    """Daily watch rows built from entered readings: 42 days at the usual values with normal day-to-day
    wobble (so the twin can learn a normal range), then the last 3 days at the readings now."""
    rng = np.random.default_rng(7)
    sd = {"hr": 3.0, "rr": 0.8, "spo2": 0.6, "steps": 0.15, "puffs": 0.3, "sleep": 0.5}   # steps: share of usual
    vals = {}
    for k, u in usual.items():
        v = np.clip(u + rng.normal(0, sd[k], n_days) * (u if k == "steps" else 1), 0, None)
        v[-3:] = now[k]
        vals[k] = v
    taken = np.full(n_days, float(prescribed))
    taken[-7:] = doses_7d / 7 if prescribed else 0
    return pd.DataFrame({"patient_id": "NEW-0001", "date": pd.date_range(end=end_day, periods=n_days), "city": city,
                         "heart_rate_bpm": vals["hr"], "resp_rate_bpm": vals["rr"], "spo2_pct": np.clip(vals["spo2"], 0, 100),
                         "steps": vals["steps"], "sleep_hours": vals["sleep"], "systolic_bp": np.nan, "diastolic_bp": np.nan,
                         "rescue_puffs": vals["puffs"], "controller_doses_taken": taken, "controller_doses_prescribed": prescribed})


OTHER_CITIES = {"Jaipur": (26.91, 75.79), "Ahmedabad": (23.02, 72.57), "Pune": (18.52, 73.86), "Bhopal": (23.26, 77.41),
                "Chandigarh": (30.73, 76.78), "Kanpur": (26.45, 80.33), "Varanasi": (25.32, 82.97), "Guwahati": (26.14, 91.74),
                "Bhubaneswar": (20.30, 85.82), "Nagpur": (21.15, 79.09), "Kochi": (9.93, 76.27), "Coimbatore": (11.02, 76.96),
                "Visakhapatnam": (17.69, 83.22), "Indore": (22.72, 75.86), "Ranchi": (23.34, 85.31), "Thiruvananthapuram": (8.52, 76.94)}

# ------------------------------------------------------------------ sidebar
st.sidebar.markdown(f"<h2 style='margin:0'>BreatheTwin</h2><div class='muted'>COPD digital twin · Team MOMENTUM</div>",
                    unsafe_allow_html=True)
PAGE_LABEL = {"Command centre": "Overview: all patients", "Patient twin": "One patient in detail",
              "Twin Lab (what-if)": "What-if lab", "Add a patient": "Check a new person", "Devices": "Devices and sensors", "Model and evidence": "How it works"}
st.sidebar.markdown("<p class='muted' style='margin-top:0.4rem'>Warns doctors and families 1 to 3 days before a COPD "
                    "flare-up, explains why, and shows what would lower the risk.</p>", unsafe_allow_html=True)
QP = st.query_params
page = st.sidebar.radio("Go to", list(PAGE_LABEL), format_func=PAGE_LABEL.get,
                        index=list(PAGE_LABEL).index(QP["page"]) if QP.get("page") in PAGE_LABEL else 0)
dates = list(pd.date_range(START_DATE, END_DATE).date)
day = pd.Timestamp(st.sidebar.select_slider("Replay date", options=dates, value=pd.Timestamp(QP.get("day", "2019-11-05")).date(),
                                            help="Pretend 'today' is this date. The twin replays a real year of Indian air pollution and weather "
                                                 "(Mar 2019 to Feb 2020) so you can see how risk changes with the seasons."))
today = risk[risk.date == day].merge(patients[["patient_id", "display_name", "age", "gold_stage", "exacerbations_prior_year"]],
                                     on="patient_id")
order = today.assign(ill=today.level.eq("In flare-up")).sort_values(["ill", "risk"], ascending=[True, False])
labels = {r.patient_id: f"{r.display_name}, {r.age} yrs, {r.city} · {r.level} ({r.risk:.0%})" for r in order.itertuples()}
if QP.get("pid") in labels and "pid" not in st.session_state:
    st.session_state.pid = QP["pid"]
if "pid" not in st.session_state or st.session_state.pid not in labels:
    # open on a high-risk patient whose risk is not already near certain, so changes are visible
    pick = order[(order.level == "High") & (order.risk < 0.5)]
    st.session_state.pid = (pick if len(pick) else order).patient_id.iloc[0]
if page in ("Patient twin", "Twin Lab (what-if)"):
    st.sidebar.selectbox("Patient", list(labels), format_func=labels.get, key="pid")
st.sidebar.markdown("<div class='legend' style='margin-top:0.8rem'><b>Risk levels</b><br>" + "".join(
    f"<div style='margin:0.25rem 0'>{chip(k)} <span class='muted'>{v}</span></div>" for k, v in LEVEL_MEANING.items()) + "</div>",
    unsafe_allow_html=True)
with st.sidebar.expander("Medical words explained"):
    for k, v in GLOSSARY.items():
        st.markdown(f"**{k}**: {v}")
st.sidebar.markdown("<p class='muted' style='margin-top:1rem'>Air quality (CPCB) and weather (Open-Meteo) are real. "
                    "Patients come from Synthea; watch readings and flare-ups are simulated from published studies. "
                    "The twin is stress-tested on 100 real de-identified hospital patients (MIMIC-III demo).</p>",
                    unsafe_allow_html=True)
pid = st.session_state.pid


# ================================================================== COMMAND CENTRE
if page == "Command centre":
    band("Overview: all patients", f"{len(patients)} COPD patients across 8 Indian cities, ranked by risk of a flare-up in the next 3 days")
    howto("How to read this page", [
        "Every person here has <b>COPD</b>, a long-term lung disease. A <b>flare-up</b> is a sudden worsening of breathing that often needs a doctor.",
        "Each day the twin compares every patient's watch readings with <b>their own normal</b>, adds their city's air pollution and weather, "
        "and gives a <b>% chance of a flare-up in the next 3 days</b>.",
        "Start with <b>Call these patients today</b> on the right: the people most at risk, and the main reason why.",
        "Move the <b>Replay date</b> on the left to see how risk rises in the smoggy, cold winter months.",
    ])
    e_today = env[env.date == day].set_index("city")
    active = today[today.level != "In flare-up"]
    prev = risk[risk.date == day - pd.Timedelta(days=7)]
    hi_now, hi_prev = int((today.level == "High").sum()), int((prev.level == "High").sum())
    worst = e_today.pm25.idxmax()
    c = st.columns(5)
    kpi(c[0], hi_now, "High-risk patients", f"{hi_now - hi_prev:+d} vs a week ago", RISK["High"])
    kpi(c[1], f"{active.risk.sum():.1f}", "Flare-ups expected in the next 3 days", "everyone's chances added up")
    kpi(c[2], int((today.level == "In flare-up").sum()), "In a flare-up today", "", RISK["In flare-up"])
    kpi(c[3], f"{e_today.pm25.max():.0f}", f"Most polluted city today: {worst}", f"PM2.5 µg/m³ · {e_today.pm25_category[worst]} · safe level is 15", SMOG)
    kpi(c[4], f"{e_today.temp_min_c.min():.0f}°C", f"Coldest night: {e_today.temp_min_c.idxmin()}",
        f"biggest 3-week drop: {env[env.date == day].set_index('city').temp_change_c.abs().idxmax()}")

    gs = patients.gold_stage.value_counts(normalize=True).sort_index()
    st.markdown(f"<p class='muted' style='margin:0.6rem 0 0.2rem'><b>Who is being monitored (health records):</b> "
                f"ages {patients.age.min()} to {patients.age.max()} · severity GOLD 1/2/3/4: "
                f"{' / '.join(f'{v:.0%}' for v in gs.values)} · current smokers {(patients.smoking_status == 'current').mean():.0%} · "
                f"cooking smoke at home {patients.biomass_fuel_exposure.mean():.0%} · high eosinophils "
                f"{(patients.blood_eosinophils_per_ul >= 300).mean():.0%} · flu vaccine {patients.influenza_vaccinated.mean():.0%} · "
                f"2+ flare-ups last year {(patients.exacerbations_prior_year >= 2).mean():.0%}</p>", unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("### Risk and air across India")
        by_city = today.groupby("city").agg(high=("level", lambda s: (s == "High").sum()), n=("risk", "size"),
                                            mean_risk=("risk", "mean")).reindex(CITIES)
        lat = [CITIES[cname]["lat"] for cname in CITIES]; lon = [CITIES[cname]["lon"] for cname in CITIES]
        fig = go.Figure(go.Scattergeo(
            lat=lat, lon=lon, text=list(CITIES), mode="markers+text", textposition="middle right",
            marker=dict(size=14 + by_city.high.values * 9, color=e_today.pm25.reindex(CITIES).values, colorscale=AQI_SCALE,
                        cmin=0, cmax=400, line=dict(color="white", width=1.5),
                        colorbar=dict(title="PM2.5<br>µg/m³", thickness=10, len=0.7)),
            customdata=np.stack([by_city.high, by_city.n, e_today.pm25.reindex(CITIES), e_today.temp_min_c.reindex(CITIES)], -1),
            hovertemplate="<b>%{text}</b><br>%{customdata[0]} high-risk of %{customdata[1]}<br>PM2.5 %{customdata[2]:.0f} µg/m³"
                          "<br>Night low %{customdata[3]:.0f}°C<extra></extra>"))
        fig.update_geos(scope="asia", projection_type="mercator", lataxis_range=[7, 34], lonaxis_range=[67, 95],
                        showcountries=True, countrycolor="#9FB3C0", showland=True, landcolor="#F4F7F9",
                        showocean=True, oceancolor="#DCE8EF", showframe=False, resolution=50)
        base_layout(fig, 430)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("<p class='muted'>Bigger bubble = more high-risk patients in that city. Colour = today's air pollution "
                    "(PM2.5, µg/m³): green is clean, red and purple are severe. Hover over a city for details.</p>", unsafe_allow_html=True)
    with right:
        st.markdown("### Call these patients today")
        st.markdown("<p class='muted'>The % is the chance of a flare-up in the next 3 days. The grey line is the main reason. "
                    "Open <b>One patient in detail</b> to see the full picture.</p>", unsafe_allow_html=True)
        bands = {"All ages": (0, 200), "30-44": (30, 44), "45-59": (45, 59), "60-74": (60, 74), "75 and over": (75, 200)}
        band_pick = st.radio("Age group", list(bands), horizontal=True, label_visibility="collapsed")
        lo, hi = bands[band_pick]
        shown = active[active.age.between(lo, hi)].sort_values("risk", ascending=False).head(7)
        if shown.empty:
            st.markdown("<p class='muted'>No patients in this age group today.</p>", unsafe_allow_html=True)
        for r in shown.itertuples():
            a = assess_cached(r.patient_id, day)
            why = a["triggers"][0]["text"] if a["triggers"] else "No single trigger stands out"
            st.markdown(f'<div class="alert" style="border-left-color:{RISK[r.level]}"><div class="pct" style="color:{RISK[r.level]}">'
                        f'{r.risk:.0%}</div><div><div class="who">{r.display_name}, {r.age} yrs · {r.city}</div>'
                        f'<div class="why">{why}</div>'
                        f'<div class="why" style="font-size:0.8rem">Record: {" · ".join(record_tags(P.loc[r.patient_id]))}</div></div></div>',
                        unsafe_allow_html=True)

    st.markdown("### Smog and cold warnings: next 3 days")
    adv = all_cities(env, day, list(CITIES))
    warn = {c: s for c, s in adv.items() if s["level"] != "ok"}
    if not adv:
        st.markdown("<p class='muted'>No later days to look ahead to: this is the last day of the replay year.</p>", unsafe_allow_html=True)
    elif not warn:
        st.markdown("<div class='card'>✅ No smog or cold snap expected in any of the 8 cities in the next 3 days.</div>", unsafe_allow_html=True)
    else:
        wc = st.columns(2)
        for i, (c, s_) in enumerate(warn.items()):
            with wc[i % 2]:
                advisory_card(s_)
        calm = [c for c, s_ in adv.items() if s_["level"] == "ok"]
        if calm:
            st.markdown(f"<p class='muted'>No warning for: {', '.join(calm)}.</p>", unsafe_allow_html=True)
    st.markdown(f"<p class='muted'>{FORECAST_NOTE} Patients in warned cities can be messaged with this advice in advance.</p>",
                unsafe_allow_html=True)

    st.markdown("### The year at a glance")
    st.markdown("<p class='muted'>Brown bars: average air pollution across the 8 cities. Lines: how many patients were high risk "
                "or in a flare-up. Both climb together in winter. The dotted line marks the replay date.</p>", unsafe_allow_html=True)
    yr = risk.groupby("date").agg(high=("level", lambda s: (s == "High").sum()), ill=("level", lambda s: (s == "In flare-up").sum()))
    pm_nat = env.groupby("date").pm25.mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=pm_nat.index, y=pm_nat.values, name="Average PM2.5, 8 cities (µg/m³)", marker_color=SMOG, opacity=0.35, yaxis="y2"))
    fig.add_trace(go.Scatter(x=yr.index, y=yr.ill.rolling(7, min_periods=1).mean(), name="Patients in a flare-up (7-day avg)",
                             line=dict(color=RISK["In flare-up"], width=2.5)))
    fig.add_trace(go.Scatter(x=yr.index, y=yr.high.rolling(7, min_periods=1).mean(), name="High-risk patients (7-day avg)",
                             line=dict(color=RISK["High"], width=2.5)))
    fig.add_vline(x=day, line=dict(color=INK, dash="dot"))
    base_layout(fig, 300, legend=dict(orientation="h", y=1.12), yaxis2=dict(overlaying="y", side="right", showgrid=False, title="PM2.5 (µg/m³)"))
    st.plotly_chart(fig, use_container_width=True)


# ================================================================== PATIENT TWIN
elif page == "Patient twin":
    p = P.loc[pid]
    a = assess_cached(pid, day)
    r = a["row"]
    ill = bool(wear[(wear.patient_id == pid) & (wear.date == day)].in_exacerbation.iloc[0])
    status = "is in a flare-up today" if ill else f"{a['level'].lower()} risk of a flare-up in the next 3 days"
    band(f"{p.display_name}, {p.age} yrs, {p.city}: {status}",
         f"GOLD {p.gold_stage} {p.copd_type.lower()} · {p.exacerbations_prior_year} flare-ups last year · "
         f"smoking {p.smoking_status} ({p.tobacco_type}) · cooking smoke {'yes' if p.biomass_fuel_exposure else 'no'} · "
         f"eosinophils {p.blood_eosinophils_per_ul}/µL")

    howto("How to read this page", [
        f"The dial is the <b>chance of a flare-up in the next 3 days</b>. The black mark on the dial is the alert line ({THR:.1%}); "
        f"above it the patient is flagged High. {LEVEL_MEANING.get(a['level'], '')}",
        "The four boxes show today's body readings next to this person's <b>own normal</b> (their usual over the past month). "
        "Red text means worse than usual, green means fine.",
        "<b>Health record (EHR)</b> shows the fixed facts from the hospital record (severity, smoking, blood tests, other illnesses, "
        "medicines) that set this person's starting level of risk.",
        "<b>What is pushing the risk</b>: red bars to the right raise the risk, green bars to the left lower it. Longer bar, bigger effect.",
        "In the charts at the bottom, the shaded band is the person's normal range. Dots outside the band are unusual.",
    ])
    g1, g2 = st.columns([1, 2.2])
    with g1:
        yest = assess_cached(pid, day - pd.Timedelta(days=1))["prob"]
        st.plotly_chart(gauge(a["prob"], ref=yest), use_container_width=True)
        st.markdown(f"<p class='muted'>Black mark: alert line ({THR:.1%}). The small number under the % is the change since yesterday.</p>",
                    unsafe_allow_html=True)
    with g2:
        vc = st.columns(4)
        for col, (s, name, unit, fmt, good_up) in zip(vc, [("rr", "Breathing rate", "breaths/min", ".1f", False), ("spo2", "Blood oxygen (SpO2)", "%", ".1f", True),
                                                           ("hr", "Resting heart rate", "bpm", ".0f", False), ("steps", "Steps", "today", ".0f", True)]):
            colname = {"rr": "resp_rate_bpm", "spo2": "spo2_pct", "hr": "heart_rate_bpm", "steps": "steps"}[s]
            now, norm = r[colname], r[f"{s}_normal"]
            d = (now - norm) if pd.notna(now) else np.nan
            bad = (d < 0) if good_up else (d > 0)
            colr = UP if bad and abs(d) > {"rr": 1.5, "spo2": 1, "hr": 4, "steps": 600}[s] else DOWN if pd.notna(d) else "#536673"
            col.markdown(f'<div class="vital"><div class="n">{name}</div><div class="x">{now:{fmt}}<span class="muted"> {unit}</span></div>'
                         f'<div class="d" style="color:{colr}">{d:+{fmt}} vs own normal {norm:{fmt}}</div></div>' if pd.notna(now)
                         else f'<div class="vital"><div class="n">{name}</div><div class="x">no data</div><div class="muted">watch not worn</div></div>',
                         unsafe_allow_html=True)
        st.write("")
        rc = st.columns([1.2, 1])
        with rc[0]:
            st.markdown("**Checks against own normal**")
            show_checks(a["rules"], a["prob"])
        with rc[1]:
            st.markdown("**What would lower the risk**")
            show_scenarios(a["prob"], a["scenarios"])

    st.markdown("### Health record (EHR)")
    src_note = ("Record generated by Synthea (synthetic hospital records), with India-specific fields added by us"
                if p.record_source == "Synthea" else "Synthetic record drawn by us (India overlay, younger patients)")
    rec_push = a["groups"].get("Clinical history", 0)
    st.markdown(f"<p class='muted'>The fixed part of the twin: what the hospital record says about this person. It sets the "
                f"starting level of risk, and the daily readings move it up or down. For {p.display_name}, the record "
                f"{'raises' if rec_push > 0 else 'lowers'} today's risk x{np.exp(rec_push):.2f} compared with an average patient. "
                f"Source: {src_note}.</p>", unsafe_allow_html=True)

    def rec_card(col, title, items):
        rows = "".join(f"<tr><td class='muted' style='padding:0.15rem 0.6rem 0.15rem 0'>{k}</td><td><b>{v}</b></td></tr>"
                       for k, v in items if v not in (None, ""))
        col.markdown(f"<div class='card' style='height:100%'><div style='font-weight:700;margin-bottom:0.3rem'>{title}</div>"
                     f"<table style='font-size:0.9rem'>{rows}</table></div>", unsafe_allow_html=True)

    yn = lambda v: "yes" if v else "no"
    conds = [n for k, n in [("hypertension", "high blood pressure"), ("diabetes", "diabetes"),
                            ("ischemic_heart_disease", "heart disease"), ("heart_failure", "heart failure"),
                            ("anemia", "anaemia"), ("obesity", "obesity")] if p.get(k, 0)]
    e1, e2, e3, e4 = st.columns(4)
    rec_card(e1, "Diagnosis", [
        ("COPD type", p.copd_type),
        ("Severity", f"GOLD {p.gold_stage} of 4"),
        ("Flare-ups in the last year", int(p.exacerbations_prior_year))])
    rec_card(e2, "Risk factors", [
        ("Age, sex", f"{p.age} yrs, {'male' if p.sex == 'M' else 'female'}"),
        ("Smoking", p.smoking_status + (f" ({p.tobacco_type})" if p.tobacco_type != "none" else "")),
        ("Cooking smoke at home", yn(p.biomass_fuel_exposure)),
        ("Alpha-1 gene variant", yn(p.serpina1_variant)),
        ("City", f"{p.city} ({p.region})")])
    rec_card(e3, "Tests and other conditions", [
        ("Blood eosinophils", f"{p.blood_eosinophils_per_ul} cells/µL" + (" (high)" if p.blood_eosinophils_per_ul >= 300 else "")),
        ("Haemoglobin", f"{p.hemoglobin:.1f} g/dL" if pd.notna(p.hemoglobin) else "not recorded"),
        ("BMI", f"{p.bmi:.1f} kg/m²" if pd.notna(p.bmi) else "not recorded"),
        ("Blood pressure", f"{p.systolic_bp:.0f}/{p.diastolic_bp:.0f} mmHg" if pd.notna(p.systolic_bp) else "not recorded"),
        ("Other conditions", ", ".join(conds) if conds else "none recorded")])
    rec_card(e4, "Treatment and prevention", [
        ("Daily (controller) inhaler", yn(p.on_maintenance_inhaler)),
        ("Rescue inhaler", yn(p.on_rescue_inhaler)),
        ("Home oxygen", yn(p.home_oxygen)),
        ("Flu vaccine this year", yn(p.influenza_vaccinated))])
    st.write("")

    o1, o2 = st.columns([1.4, 1])
    with o1:
        st.markdown(f"**Next 3 days in {p.city}**")
        s_ = summarise(p.city, outlook(env, p.city, day))
        if s_:
            advisory_card(s_)
            st.markdown(f"<p class='muted'>{FORECAST_NOTE}</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p class='muted'>Last day of the replay year: nothing to look ahead to.</p>", unsafe_allow_html=True)
    with o2:
        st.markdown("**Visit summary for the doctor**")
        st.markdown("<p class='muted'>One page with the last 30 days: readings against own normal, inhaler use, flare-ups, "
                    "the twin's alerts, air quality and questions to ask. Open it, then press Ctrl+P to print or save as PDF.</p>",
                    unsafe_allow_html=True)
        summary = build_summary_html(p, a, history_cached(pid, day), env[env.city == p.city], day, THR, s_)
        st.download_button("Download visit summary", summary, file_name=f"visit_summary_{p.display_name.replace(' ', '_')}_{day:%Y%m%d}.html",
                           mime="text/html", type="primary", use_container_width=True)

    c1, c2 = st.columns([1, 1.25])
    with c1:
        st.plotly_chart(push_chart(a["groups"]), use_container_width=True)
    with c2:
        sh = history_cached(pid, day).tail(90)
        fig = go.Figure()
        fig.add_hrect(y0=THR, y1=max(0.6, sh.risk.max() * 1.1), fillcolor="#F3DEDB", opacity=0.45, line_width=0)
        fig.add_trace(go.Scatter(x=sh.date, y=sh.risk, line=dict(color=TEAL, width=2.4), fill="tozeroy",
                                 fillcolor="rgba(31,95,122,0.08)", name="3-day risk"))
        for d0 in events[(events.patient_id == pid) & events.onset_date.between(sh.date.min(), day)].onset_date:
            fig.add_vline(x=d0, line=dict(color=RISK["In flare-up"], width=2))
            fig.add_annotation(x=d0, y=1, yref="paper", text="flare-up", showarrow=False, font=dict(color=RISK["In flare-up"], size=11))
        base_layout(fig, 330, "Risk over the last 90 days (shaded: above alert line)", showlegend=False)
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Last 30 days against own normal")
    st.markdown("<p class='muted'>Shaded band: this person's normal range. Faster breathing, lower oxygen, a higher heart rate "
                "and fewer steps than usual, together, are the classic early signs of a flare-up.</p>", unsafe_allow_html=True)
    f = a["features"].tail(30)
    s1, s2, s3, s4 = st.columns(4)
    s1.plotly_chart(signal_chart(f, "resp_rate_bpm", "rr_normal", "Breathing rate", 1.2), use_container_width=True)
    s2.plotly_chart(signal_chart(f, "spo2_pct", "spo2_normal", "Blood oxygen %", 1.0), use_container_width=True)
    s3.plotly_chart(signal_chart(f, "heart_rate_bpm", "hr_normal", "Resting heart rate", 4.9), use_container_width=True)
    s4.plotly_chart(signal_chart(f, "steps", "steps_normal", "Steps", 1200), use_container_width=True)
    ec = env[(env.city == p.city) & env.date.between(day - pd.Timedelta(days=59), day)]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=ec.date, y=ec.pm25, marker_color=SMOG, opacity=0.75, name="PM2.5 (µg/m³)"))
    fig.add_trace(go.Scatter(x=ec.date, y=ec.temp_min_c, yaxis="y2", line=dict(color=TEAL, width=2), name="Night low °C"))
    wd = wear[(wear.patient_id == pid) & wear.date.between(day - pd.Timedelta(days=59), day)]
    fig.add_trace(go.Scatter(x=wd.date, y=wd.controller_doses_taken, yaxis="y3", mode="markers", name="Inhaler doses taken",
                             marker=dict(color=INK, size=5, symbol="line-ns-open")))
    base_layout(fig, 260, f"{p.city}: air, cold and inhaler use, last 60 days", legend=dict(orientation="h", y=-0.25),
                yaxis=dict(title="PM2.5 (µg/m³)", gridcolor=MIST), yaxis2=dict(overlaying="y", side="right", showgrid=False, title="°C"),
                yaxis3=dict(overlaying="y", side="right", range=[-6, 3], visible=False))
    st.plotly_chart(fig, use_container_width=True)


# ================================================================== TWIN LAB
elif page == "Twin Lab (what-if)":
    p = P.loc[pid]
    a = assess_cached(pid, day)
    r0 = a["row"]
    band(f"What-if lab: {p.display_name}, {p.age} yrs, {p.city}",
         "Move any slider and the twin re-scores the risk instantly. Starts from the patient's real state on the replay date.<br>"
         f"Record: {' · '.join(record_tags(p))}")

    howto("How to use the what-if lab", [
        "Ask 'what if' questions safely. Each slider changes one thing, and the dial shows how this patient's risk would change. "
        "Nothing here changes the real record.",
        "The buttons load ready-made situations, for example a <b>Smog week</b> or <b>Stopped inhaler</b>. <b>Reset to today</b> undoes everything.",
        "Body-signal sliders are <b>changes from the person's own normal</b>: +3 breaths/min means 3 more breaths a minute than usual.",
        "The three curves at the bottom show how risk rises or falls as one thing changes. The dot is where the patient is now.",
    ])
    rr_sd = abs(r0.rr_dev3 / r0.rr_z3) if r0.rr_z3 not in (0, np.nan) and pd.notna(r0.rr_z3) else 1.2
    defaults = {
        "rr": float(np.round(np.nan_to_num(r0.rr_dev3), 1)), "spo2": float(np.round(np.nan_to_num(r0.spo2_dev3), 1)),
        "hr": float(np.round(np.nan_to_num(r0.hr_dev3), 0)), "steps": int(np.round(np.nan_to_num(r0.steps_dev3), -2)),
        "puffs": float(np.round(np.clip(np.nan_to_num(r0.rescue_3d_vs_normal), 0, 6), 1)),
        "adh": int(round(r0.adherence_7d * 100)), "pm7": int(r0.pm25_lag2_7), "pm": int(r0.pm25),
        "drop": int(round(r0.temp_drop_21d)), "tmin": int(round(r0.temp_min_c)), "rh": int(round(r0.humidity_pct)),
        "gold": int(r0.gold_stage), "prior": int(r0.exacerbations_prior_year), "smoker": bool(r0.smoker_current),
        "biomass": bool(r0.biomass_fuel_exposure), "vacc": bool(r0.influenza_vaccinated),
        "age": int(r0.age), "eos": int(r0.blood_eosinophils_per_ul), "comorb": int(r0.comorbidity_count),
        "bmi": float(round(r0.bmi, 1)) if pd.notna(r0.bmi) else 22.0, "oxygen": bool(r0.home_oxygen),
    }
    key = f"lab_{pid}_{day.date()}"
    if st.session_state.get("lab_key") != key:
        st.session_state.lab_key = key
        for k, v in defaults.items():
            st.session_state[f"lab_{k}"] = v

    presets = {
        "Reset to today": {},
        "Smog week": {"pm7": 350, "pm": 380},
        "Cold snap": {"drop": 25, "tmin": 5},
        "Stopped inhaler": {"adh": 10},
        "Early warning signs": {"rr": 3.5, "spo2": -2.0, "hr": 7.0, "puffs": 2.0, "steps": -800},
        "Perfect week": {"rr": 0.0, "spo2": 0.0, "hr": 0.0, "puffs": 0.0, "adh": 100, "pm7": 30, "pm": 30, "drop": 0},
    }
    pc = st.columns(len(presets))
    for col, (name, vals) in zip(pc, presets.items()):
        if col.button(name, use_container_width=True):
            for k, v in (defaults if name == "Reset to today" else vals).items():
                st.session_state[f"lab_{k}"] = v
            st.rerun()

    ctrl, out = st.columns([1, 1.45])
    with ctrl:
        t1, t2, t3, t4 = st.tabs(["Body signals", "Inhaler", "Air and weather", "Patient record"])
        with t1:
            st.slider("Breathing rate vs own normal (breaths/min)", -3.0, 8.0, step=0.1, key="lab_rr",
                      help="0 = usual. Breathing 2-4 breaths a minute faster than usual often comes 1-3 days before a flare-up.")
            st.slider("Blood oxygen vs own normal (% points)", -6.0, 2.0, step=0.1, key="lab_spo2",
                      help="0 = usual. A drop of 2 or more points below usual is a warning sign.")
            st.slider("Resting heart rate vs own normal (bpm)", -10.0, 25.0, step=1.0, key="lab_hr")
            st.slider("Daily steps vs own normal", -3000, 1500, step=100, key="lab_steps")
            st.slider("Extra rescue inhaler puffs per day", 0.0, 6.0, step=0.1, key="lab_puffs",
                      help="Puffs of the quick-relief inhaler above the usual daily amount.")
        with t2:
            st.slider("Controller doses taken this week (%)", 0, 100, step=5, key="lab_adh",
                      disabled=not bool(r0.controller_doses_prescribed))
            if not r0.controller_doses_prescribed:
                st.caption("This patient has no maintenance inhaler prescribed.")
        with t3:
            st.slider("PM2.5, average of last week (µg/m³)", 0, 600, step=5, key="lab_pm7",
                      help="Air pollution affects the lungs with a delay of 2 to 7 days, so last week's air matters most. Safe level is 15, India's limit 60.")
            st.slider("PM2.5 today (µg/m³)", 0, 600, step=5, key="lab_pm")
            st.slider("Total temperature drop over 3 weeks (°C)", 0, 40, step=1, key="lab_drop")
            st.slider("Night low temperature (°C)", 0, 32, step=1, key="lab_tmin")
            st.slider("Humidity (%)", 10, 100, step=1, key="lab_rh")
        with t4:
            st.select_slider("GOLD stage", [1, 2, 3, 4], key="lab_gold")
            st.slider("Flare-ups in the last year", 0, 6, key="lab_prior")
            st.toggle("Current smoker", key="lab_smoker")
            st.toggle("Cooking smoke exposure", key="lab_biomass")
            st.toggle("Flu vaccine this year", key="lab_vacc")
            st.slider("Age (years)", 30, 100, key="lab_age")
            st.slider("Blood eosinophils (cells/µL)", 0, 1000, step=10, key="lab_eos",
                      help="From a routine blood count. 300 or more is high and linked to more flare-ups.")
            st.slider("Number of other long-term conditions", 0, 6, key="lab_comorb",
                      help="For example high blood pressure, diabetes, heart disease, heart failure, anaemia, obesity.")
            st.slider("BMI (kg/m²)", 12.0, 45.0, step=0.5, key="lab_bmi")
            st.toggle("On home oxygen", key="lab_oxygen")

    S = {k: st.session_state[f"lab_{k}"] for k in defaults}
    changed = {k for k in defaults if S[k] != defaults[k]}
    r = r0.copy()
    for s_ in ["rr", "spo2", "hr", "steps"]:
        if s_ in changed:
            z = r0[f"{s_}_z3"]
            old_sd = abs(r0[f"{s_}_dev3"] / z) if pd.notna(z) and z != 0 else {"rr": 1.2, "spo2": 1.0, "hr": 4.9, "steps": 1500}[s_]
            r[f"{s_}_dev1"] = r[f"{s_}_dev3"] = S[s_]
            r[f"{s_}_z3"] = S[s_] / max(old_sd, 1e-3)
    setters = {"puffs": ("rescue_3d_vs_normal", lambda v: v), "adh": ("adherence_7d", lambda v: v / 100),
               "pm7": ("pm25_lag2_7", lambda v: v), "pm": ("pm25", lambda v: v), "drop": ("temp_drop_21d", lambda v: v),
               "tmin": ("temp_min_c", lambda v: v), "rh": ("humidity_pct", lambda v: v), "gold": ("gold_stage", lambda v: v),
               "prior": ("exacerbations_prior_year", lambda v: v), "smoker": ("smoker_current", int),
               "biomass": ("biomass_fuel_exposure", int), "vacc": ("influenza_vaccinated", int),
               "age": ("age", lambda v: v), "eos": ("blood_eosinophils_per_ul", lambda v: v),
               "comorb": ("comorbidity_count", lambda v: v), "bmi": ("bmi", lambda v: v), "oxygen": ("home_oxygen", int)}
    for k, (col_, fn) in setters.items():
        if k in changed:
            r[col_] = fn(S[k])
    if {"rh", "tmin"} & changed:
        r["humid_heat"] = int(S["rh"] >= 80 and S["tmin"] >= 24)

    prob, _, groups = score_row(r)
    with out:
        o1, o2 = st.columns([1.05, 1])
        with o1:
            st.plotly_chart(gauge(prob, ref=a["prob"], title="Risk with your changes (delta vs real today)"), use_container_width=True)
        with o2:
            lv = risk_level(prob)
            st.markdown(f"<div class='card'><div class='muted'>Twin verdict</div><div style='font-family:Source Serif 4,serif;"
                        f"font-size:1.5rem;margin:0.2rem 0'>{chip(lv)} {'Call the patient today' if lv == 'High' else 'Watch closely' if lv == 'Medium' else 'Routine follow-up'}</div>"
                        f"<div class='muted'>Real risk today {a['prob']:.1%} · with changes {prob:.1%} · "
                        f"{'x%.1f' % (prob / a['prob']) if a['prob'] > 0 else ''}</div></div>", unsafe_allow_html=True)
            vals = dict(r); vals.update(spo2_now=np.nan, prescribed=r0.controller_doses_prescribed)
            show_checks(rule_checks(vals), prob, limit=4)
        st.plotly_chart(push_chart(groups, 400), use_container_width=True)

    st.markdown("### How risk responds to each lever")
    st.markdown("<p class='muted'>Each curve changes one thing and keeps everything else as it is. The dotted red line is the alert line.</p>",
                unsafe_allow_html=True)
    w1, w2, w3 = st.columns(3)

    def response(col, title, xs, ys, now_x, xlabel, fmt="%{x}"):
        fig = go.Figure(go.Scatter(x=xs, y=ys, line=dict(color=TEAL, width=2.6), fill="tozeroy", fillcolor="rgba(31,95,122,0.08)",
                                   hovertemplate=f"{xlabel} {fmt}<br>risk %{{y:.1%}}<extra></extra>"))
        fig.add_hline(y=THR, line=dict(color=RISK["High"], dash="dot", width=1))
        i = int(np.argmin(np.abs(np.asarray(xs) - now_x)))
        fig.add_trace(go.Scatter(x=[xs[i]], y=[ys[i]], mode="markers", marker=dict(size=12, color=RISK[risk_level(ys[i])],
                                                                                  line=dict(color="white", width=2)), hoverinfo="skip"))
        base_layout(fig, 250, title, showlegend=False)
        fig.update_yaxes(tickformat=".0%", rangemode="tozero"); fig.update_xaxes(title=xlabel)
        col.plotly_chart(fig, use_container_width=True)

    xs = np.arange(0, 501, 10)
    response(w1, "Air pollution", xs, sweep(r, "pm25_lag2_7", xs, {"pm25": lambda v: v}), S["pm7"], "PM2.5 (µg/m³)")
    xs2 = np.linspace(0, 1, 21)
    response(w2, "Inhaler adherence", xs2 * 100, sweep(r, "adherence_7d", xs2), S["adh"], "doses taken (%)")
    xs3 = np.round(np.arange(-2, 8.01, 0.5), 1)
    ys3 = sweep(r, "rr_dev3", xs3, {"rr_dev1": lambda v: v, "rr_z3": lambda v: v / max(rr_sd, 1e-3)})
    response(w3, "Breathing rate", xs3, ys3, S["rr"], "breaths/min above own normal")
    st.markdown("<p class='muted'>Body signals, inhaler and weather effects are learned by the model from the simulated cohort. "
                "The air-pollution effect is the published dose-response (+2.5% risk per 10 µg/m³ PM2.5, DeVries 2017), "
                "so its curve is smooth by design. These are model estimates for decision support, not clinical advice.</p>",
                unsafe_allow_html=True)


# ================================================================== ADD A PATIENT
elif page == "Add a patient":
    band("Check a new person", "Enter the record, the patient's usual readings when well, and their readings now. "
                          "The twin compares the two and scores the risk of a flare-up in the next 3 days.")
    howto("How to check a new person", [
        "Fill in what you know. The boxes start at typical values, so anything you leave alone is treated as average.",
        "<b>Usual</b> = readings on a normal good day. <b>Now</b> = the average of the last 3 days. The twin looks at the <b>change</b>, "
        "so if Now equals Usual the risk stays low.",
        "Heart rate and blood oxygen come from a smartwatch or a finger pulse oximeter. For breathing rate, count breaths for one minute while resting.",
        "For air quality, copy the <b>PM2.5</b> number (µg/m³) from a CPCB or AQI app, or use the replay data.",
    ])
    with st.form("onboard"):
        st.markdown("**1. Health record**")
        a1, a2, a3, a4 = st.columns(4)
        name = a1.text_input("Name", "New patient")
        age = a2.number_input("Age (years)", 1, 100, 64)
        sex = a3.selectbox("Sex", ["M", "F"])
        all_cities = sorted(list(CITIES) + list(OTHER_CITIES))
        city_in = a4.selectbox("City", all_cities, index=all_cities.index("Delhi"))
        gold = a1.selectbox("GOLD stage (1 mild to 4 very severe)", [1, 2, 3, 4], index=1,
                            help="From the breathing (spirometry) test report. If unknown, 2 is the most common stage.")
        prior = a2.number_input("Flare-ups in the last year", 0, 10, 1,
                                help="Times breathing got suddenly worse and needed extra medicine, a doctor visit or hospital.")
        smoking = a3.selectbox("Smoking", ["never", "former", "current"], index=1)
        eos = a4.number_input("Blood eosinophils (cells/µL)", 0, 2000, 220,
                              help="From a routine blood count (CBC) report. If unknown, leave at 220, a typical value.")
        bmi = a1.number_input("BMI (kg/m²)", 10.0, 50.0, 22.0, step=0.5)
        maint = a2.checkbox("Prescribed a daily (controller) inhaler", value=True,
                            help="The inhaler taken every day to keep COPD stable, not the quick-relief one.")
        biomass = a3.checkbox("Cooks with wood, dung or kerosene")
        vacc = a4.checkbox("Flu vaccine this year")
        oxygen = a1.checkbox("On home oxygen")
        comorb = st.multiselect("Other conditions", ["hypertension", "diabetes", "ischemic_heart_disease", "heart_failure", "anemia"])

        st.markdown("**2. Readings: usual (when well) and now (average of the last 3 days)**")
        sig = [("hr", "Resting heart rate (bpm)", 30, 180, 78, 1),
               ("rr", "Breathing rate (breaths/min)", 6.0, 50.0, 16.0, 0.5),
               ("spo2", "Blood oxygen, SpO2 (%)", 70.0, 100.0, 95.0, 0.5),
               ("steps", "Steps per day", 0, 30000, 4000, 250),
               ("puffs", "Rescue inhaler puffs per day", 0.0, 30.0, 1.0, 0.5),
               ("sleep", "Sleep (hours per night)", 0.0, 14.0, 6.5, 0.5)]
        usual, now = {}, {}
        for k, label, lo, hi, dflt, stp in sig:
            r1, r2, r3 = st.columns([1.6, 1, 1])
            r1.markdown(f"<div style='padding-top:1.9rem'>{label}</div>", unsafe_allow_html=True)
            usual[k] = r2.number_input("Usual", lo, hi, dflt, step=stp, key=f"u_{k}")
            now[k] = r3.number_input("Now", lo, hi, dflt, step=stp, key=f"n_{k}")
        doses = st.slider("Controller inhaler doses taken in the last 7 days (out of 14 prescribed)", 0, 14, 12,
                          help="Ignored if no daily inhaler is prescribed.")

        st.markdown("**3. Air quality**")
        aq = st.radio("PM2.5 source", [f"Use the replay year's real data for the city on {day:%d %b %Y}",
                                       "Enter today's PM2.5 myself (from a CPCB / AQI app)"])
        q1, q2 = st.columns(2)
        pm_today = q1.number_input("PM2.5 today (µg/m³)", 0, 999, 60)
        pm_week = q2.number_input("PM2.5, average over the past week (µg/m³)", 0, 999, 60)
        st.caption("PM2.5 is measured in micrograms per cubic metre (µg/m³). AQI apps often show an AQI number instead: "
                   "copy the PM2.5 concentration, not the AQI.")

        feed = st.radio("Data used for the assessment",
                        ["The readings entered above", "Upload a CSV of daily watch data",
                         "Simulated demo feed (not this patient's readings)"])
        up = st.file_uploader("CSV columns: date, heart_rate_bpm, resp_rate_bpm, spo2_pct, steps, sleep_hours, rescue_puffs, controller_doses_taken")
        go_btn = st.form_submit_button("Create twin and assess", type="primary")

    if go_btn:
        model_city = city_in if city_in in CITIES else nearest_city(*OTHER_CITIES[city_in])
        if model_city != city_in:
            st.info(f"{city_in} uses weather (and replay air quality) from {model_city}, the nearest monitored city in this demo.")
        if age < 30:
            st.warning("COPD is very rare under 30 and almost never diagnosed in children. The model was trained on patients aged "
                       "30 to 92, so for younger patients it treats age as if they were the youngest in training. "
                       "Read the result with care.")
        prescribed = 2 if maint else 0
        row = {"patient_id": "NEW-0001", "display_name": name, "age": age, "sex": sex, "city": model_city, "gold_stage": gold,
               "exacerbations_prior_year": prior, "smoking_status": smoking, "biomass_fuel_exposure": int(biomass),
               "blood_eosinophils_per_ul": eos, "influenza_vaccinated": int(vacc), "home_oxygen": int(oxygen), "bmi": bmi,
               **{c: int(c in comorb) for c in ["hypertension", "diabetes", "ischemic_heart_disease", "heart_failure", "anemia"]},
               "obesity": int(bmi >= 30), "heart_rate": usual["hr"], "resp_rate": usual["rr"], "systolic_bp": np.nan,
               "diastolic_bp": np.nan, "on_maintenance_inhaler": int(maint), "adherence_habit": 0.7,
               "pollution_sensitivity": 1.0, "frequent_exacerbator": int(prior >= 2)}
        p_row = pd.Series(row)
        env_c = env[env.city == model_city].copy()
        day_eval = day

        if feed.startswith("Upload"):
            if up is None:
                st.error("Choose a CSV file to upload, or pick another data option.")
                st.stop()
            h = pd.read_csv(up, parse_dates=["date"])
            h["patient_id"], h["city"] = "NEW-0001", model_city
            h["controller_doses_prescribed"] = prescribed
            for c in ["systolic_bp", "diastolic_bp"]:
                h[c] = h.get(c, np.nan)
            day_eval = h.date.max()
        elif feed.startswith("Simulated"):
            st.warning("This uses made-up watch data for a patient with this record. It does not reflect this person's readings.")
            em = env_multipliers(env.copy())
            em["norm"] = (em.m_pm25 * em.m_cold * em.m_humid).mean()
            sim, _ = simulate_patient(p_row, em[em.city == model_city].reset_index(drop=True), np.random.default_rng(SEED + 7))
            h = sim[sim.date.between(day - pd.Timedelta(days=44), day)].drop(columns=["exacerbation_onset", "in_exacerbation", "onset_within_3d"])
        else:
            h = feed_from_readings(usual, now, doses, prescribed, day, model_city)

        if aq.startswith("Enter"):
            env_c.loc[env_c.date == day_eval, "pm25"] = pm_today
            env_c.loc[env_c.date.between(day_eval - pd.Timedelta(days=7), day_eval - pd.Timedelta(days=1)), "pm25"] = pm_week

        res = assess(p_row, h, env_c[env_c.date <= day_eval])
        r = res["row"]
        st.markdown(f"### {name}, {age} yrs, {city_in}: {res['level'].lower()} risk of a flare-up in the next 3 days {chip(res['level'])}",
                    unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1.4])
        with c1:
            st.plotly_chart(gauge(res["prob"]), use_container_width=True)
            st.markdown("**Checks against own normal**")
            show_checks(res["rules"], res["prob"])
            st.markdown("**What would lower the risk**")
            show_scenarios(res["prob"], res["scenarios"])
        c2.plotly_chart(push_chart(res["groups"], 360), use_container_width=True)

        st.markdown("### What the twin read")
        used = pd.DataFrame([
            ["Resting heart rate", "bpm", r.hr_normal, r.heart_rate_bpm, r.hr_dev3],
            ["Breathing rate", "breaths/min", r.rr_normal, r.resp_rate_bpm, r.rr_dev3],
            ["Blood oxygen (SpO2)", "%", r.spo2_normal, r.spo2_pct, r.spo2_dev3],
            ["Steps", "per day", r.steps_normal, r.steps, r.steps_dev3],
            ["Sleep", "hours", r.sleep_normal, r.sleep_hours, r.sleep_dev3],
            ["Rescue inhaler", "puffs/day", np.nan, np.nan, r.rescue_3d_vs_normal],
            ["Controller doses taken, last 7 days", "%", np.nan, r.adherence_7d * 100, np.nan],
            ["PM2.5 today", "µg/m³", np.nan, r.pm25, np.nan],
            ["PM2.5, average 2 to 7 days ago", "µg/m³", np.nan, r.pm25_lag2_7, np.nan],
            ["Night low temperature", "°C", np.nan, r.temp_min_c, np.nan],
            ["Humidity", "%", np.nan, r.humidity_pct, np.nan],
        ], columns=["Signal", "Unit", "Usual", "Now / today", "Change vs usual (3-day avg)"])
        st.dataframe(used.round(1), hide_index=True, use_container_width=True)
        st.markdown("**Health record values the twin used**")
        rec_used = pd.DataFrame([
            ["Age", f"{int(r.age)} yrs"], ["Severity", f"GOLD {int(r.gold_stage)}"],
            ["Flare-ups in the last year", int(r.exacerbations_prior_year)],
            ["Current smoker", "yes" if r.smoker_current else "no"], ["Cooking smoke at home", "yes" if r.biomass_fuel_exposure else "no"],
            ["Blood eosinophils", f"{int(r.blood_eosinophils_per_ul)} cells/µL"], ["BMI", f"{r.bmi:.1f} kg/m²"],
            ["Other long-term conditions", int(r.comorbidity_count)], ["Flu vaccine this year", "yes" if r.influenza_vaccinated else "no"],
            ["Home oxygen", "yes" if r.home_oxygen else "no"],
        ], columns=["Record field", "Value"])
        rec_push = res["groups"].get("Clinical history", 0)
        st.dataframe(rec_used.astype(str), hide_index=True, use_container_width=True)
        st.caption(f"Together these {'raise' if rec_push > 0 else 'lower'} the risk x{np.exp(rec_push):.2f} compared with an average patient.")
        st.caption("Weather is the real recorded weather for the city on the replay date. The model was trained on simulated patients, "
                   "so treat the number as a demonstration of how the twin reasons, not a clinical prediction for a real person.")
        f = res["features"].tail(30)
        s1, s2 = st.columns(2)
        s1.plotly_chart(signal_chart(f, "resp_rate_bpm", "rr_normal", "Breathing rate", 1.2), use_container_width=True)
        s2.plotly_chart(signal_chart(f, "spo2_pct", "spo2_normal", "Blood oxygen %", 1.0), use_container_width=True)


# ================================================================== DEVICES AND SENSORS
elif page == "Devices":
    band("Devices and sensors", "Which wearables and home IoT devices feed the twin, and which sensor measures what")
    howto("What this page shows", [
        "<b>No needle, no blood test, nothing under the skin.</b> Every daily reading comes from a watch, a clip-on finger "
        "sensor or an inhaler add-on. Air and weather come from city sensor networks, so the patient wears nothing for those.",
        "The first table maps each signal the twin reads to the sensor that measures it and the part of the model it feeds.",
        "The second table lists devices sold in India that can supply those signals, and how their data reaches BreatheTwin.",
        "Honest note: in this prototype the watch, oximeter and inhaler readings are simulated or typed in; the device links "
        "below are the integration plan using each platform's published data interface. Air and weather data are already real.",
    ])
    st.markdown("### Three ways to equip a patient")
    kc = st.columns(3)
    for col, (name, kit, gives) in zip(kc, KITS):
        col.markdown(f"<div class='card' style='height:100%'><b style='color:{TEAL}'>{name}</b><br>{kit}"
                     f"<div class='muted' style='margin-top:0.4rem'>{gives}</div></div>", unsafe_allow_html=True)

    st.markdown("### Which sensor tracks which signal")
    sig = pd.DataFrame(SIGNALS, columns=["Signal", "Sensor that measures it", "Device", "How often", "How the twin uses it"])
    st.table(sig.set_index("Signal"))

    st.markdown("### Coverage at a glance")
    cats = ["Heart rate", "Breathing rate", "SpO2", "Steps", "Sleep", "Rescue puffs", "Controller doses", "Blood pressure"]
    cover = {
        "Fitbit / Apple / Galaxy / Garmin watch": [1, 1, 1, 1, 1, 0, 0, 0],
        "Budget watch (Noise, boAt, Amazfit)": [1, 0.5, 0.5, 1, 1, 0, 0, 0],
        "Fingertip or ring pulse oximeter": [1, 0, 1, 0, 0, 0, 0, 0],
        "Smart inhaler add-on (ADHERO, Propeller)": [0, 0, 0, 0, 0, 1, 1, 0],
        "Bluetooth BP monitor (Omron)": [1, 0, 0, 0, 0, 0, 0, 1],
        "Phone only (typed in)": [0, 0, 0, 1, 0, 0.5, 0.5, 0],
    }
    z = np.array(list(cover.values()))
    txt = np.where(z == 1, "✓", np.where(z == 0.5, "partial", ""))
    fig = go.Figure(go.Heatmap(z=z, x=cats, y=list(cover), text=txt, texttemplate="%{text}", textfont=dict(size=15, color="white"), showscale=False,
                               colorscale=[[0, "#F4F7F9"], [0.5, "#79A6B7"], [1, TEAL]], xgap=3, ygap=3, hoverinfo="skip"))
    base_layout(fig, 330)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(side="top")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Compatible devices")
    dev = pd.DataFrame(DEVICES, columns=["Type", "Examples", "Signals it gives the twin", "How the data reaches BreatheTwin", "Cost", "Note"])
    st.table(dev.set_index("Type"))

    st.markdown("### How a reading travels to the doctor")
    st.markdown(f"""<div class='card'>
    <b>Sensor</b> (watch, oximeter, inhaler clip) → <b>Bluetooth</b> → <b>patient's phone app</b> →
    <b>Android Health Connect / Apple HealthKit / vendor API</b> → <b>BreatheTwin</b> builds one daily summary per patient
    (resting heart rate, night breathing rate, morning SpO2, steps, sleep, puffs, doses) → compares it with the patient's own
    normal → <b>risk, reasons and advice</b> on the doctor's overview the same morning.<br>
    <span class='muted'>If a sensor is missing on a day, that reading stays empty and the twin works with the rest; it never treats a
    missing oxygen reading as zero. A family without a watch can type the oximeter number and a 30-second breathing count on the
    "Check a new person" page.</span></div>""", unsafe_allow_html=True)


# ================================================================== MODEL AND EVIDENCE
else:
    band("How it works", "How the twin was built, how well it performs on unseen patients, and where every number comes from")
    m = json.load(open(OUTPUTS / "metrics.json"))
    howto("What this page shows", [
        f"How well the twin works, tested on {m['patients_test']} patients it never saw while learning.",
        "<b>AUROC</b> is a score from 0.5 (a coin toss) to 1.0 (perfect) for how well the twin ranks who will have a flare-up. "
        "Published COPD tools score 0.68 to 0.85.",
        "<b>Flare-ups warned ahead</b>: of all flare-ups, how many the twin flagged 1 to 3 days before they started. "
        "<b>False alerts</b>: how often it flags someone who then does not flare up.",
        "Honest note: patient records and watch readings are simulated; air quality and weather are real.",
    ])
    c = st.columns(4)
    kpi(c[0], m["auroc"], f"Accuracy score (AUROC) on {m['patients_test']} unseen patients", "0.5 = coin toss, 1.0 = perfect; published tools 0.68 to 0.85")
    kpi(c[1], f"{m['flare_ups_warned_in_advance']:.0%}", "Flare-ups warned 1 to 3 days ahead")
    kpi(c[2], m["false_alerts_per_patient_month"], "False alerts per patient per month", "fewer than one a month")
    kpi(c[3], f"{m['patients_train']} / {m['patients_test']}", "Patients for training / testing")
    st.markdown(f"<p class='muted'>{m['caveat']}</p>", unsafe_allow_html=True)

    l, rgt = st.columns(2)
    abl = pd.DataFrame(m["single_stream_ablation"]).T.reset_index().rename(columns={"index": "Streams used"})
    fig = go.Figure(go.Bar(x=abl.auroc, y=abl["Streams used"], orientation="h", marker_color=[TEAL if "twin" in s else "#9FB7C2" for s in abl["Streams used"]],
                           text=abl.auroc, textposition="outside"))
    base_layout(fig, 300, "Prediction quality by data stream (AUROC)")
    fig.update_xaxes(range=[0.4, 1])
    l.plotly_chart(fig, use_container_width=True)
    gi = pd.Series(m["trigger_group_importance_pct"]).sort_values()
    fig = go.Figure(go.Bar(x=gi.values, y=gi.index, orientation="h", marker_color=TEAL, text=[f"{v:.0f}%" for v in gi.values], textposition="outside"))
    base_layout(fig, 300, "Share of the twin's reasoning by trigger")
    rgt.plotly_chart(fig, use_container_width=True)

    st.markdown("### How the twin works (flowchart)")
    st.image(str(ROOT / "docs" / "flowchart.png"), use_container_width=True)

    st.markdown("### How much of the data is real")
    st.dataframe(pd.DataFrame([
        ["City air quality (PM2.5, AQI)", "Real", "2,928 city-days, 8 cities, CPCB stations (1 missing day filled)", "Training and dashboard"],
        ["Weather (temperature, humidity)", "Real", "2,928 city-days, Open-Meteo archive", "Training and dashboard"],
        ["Health records", "Synthetic", "400 patients: 300 Synthea + 100 India overlay", "Training and dashboard"],
        ["Watch, oximeter and inhaler readings", "Synthetic", "146,400 patient-days, simulated from published studies", "Training and dashboard"],
        ["Flare-ups", "Synthetic", "473 simulated events", "Training labels"],
        ["Real hospital patients (stress test)", "Real", "100 de-identified ICU patients, 47,214 vital-sign readings (MIMIC-III demo)", "Testing only, never training"],
        ["Real hospital patients (record check)", "Real", "14 COPD patients (MIMIC-IV demo), aggregate comparison", "Testing only"],
    ], columns=["Data", "Real or synthetic", "Size", "Used for"]), hide_index=True, use_container_width=True)
    st.markdown("<p class='muted'>By volume, about 1% of the values the model learned from are real (all of the environment); "
                "everything about the patients is simulated. That is why the twin is stress-tested on real patients below.</p>",
                unsafe_allow_html=True)

    st.markdown("### Stress test on 100 real patients")
    stp = OUTPUTS / "stress_test_summary.json"
    if stp.exists():
        stt = json.load(open(stp))
        howto("What the stress test checks", [
            f"{stt['real_patients']} real, de-identified hospital patients ({stt['sex_mix'].get('Female', 0)} women, "
            f"{stt['sex_mix'].get('Male', 0)} men, aged 18 to 90) from the open MIMIC-III demo. The twin never saw them while learning.",
            "Their real record (COPD, heart disease, diabetes, smoking, home oxygen) and real heart rate, breathing rate and SpO2 "
            "go through the same route as the 'Check a new person' page: usual = first 24 h in hospital, now = hours 24 to 48.",
            "Air and weather are held fixed for everyone, so any difference comes from the real person, not the city.",
            stt["caveat"],
        ])
        c = st.columns(4)
        kpi(c[0], f"{stt['assessed']}/{stt['real_patients']}", "Real patients assessed", f"{stt['skipped_short_stay']} had under 48 h of vitals")
        kpi(c[1], stt["errors"] + stt["invalid_outputs"], "Crashes or invalid risks", "missing and extreme readings included")
        kpi(c[2], stt["spearman_risk_vs_worsening_signs"], "Risk vs real worsening signs (rank correlation)", "risk rises as real signs worsen")
        kpi(c[3], "Yes" if stt["edge_cases_direction_correct"] else "No", "Worse readings always raise risk", "edge-case suite")
        l, rgt = st.columns(2)
        bs = pd.DataFrame(stt["by_sex"]).rename(columns={"sex": "Group"})
        ba = pd.DataFrame(stt["by_age_group"]).rename(columns={"age_group": "Group"})
        tab = pd.concat([bs, ba])[["Group", "patients", "median_risk", "alert_rate", "worsening_rate"]]
        tab.columns = ["Group", "Patients", "Median risk", "Share alerted", "Avg. worsening signs"]
        l.markdown("**By sex and age group**")
        l.dataframe(tab, hide_index=True, use_container_width=True)
        ss = pd.DataFrame(stt["by_sex_same_warning_signs"])
        ss.columns = ["Warning signs", "Women", "Women alerted", "Men", "Men alerted"]
        ss = ss.astype(object).where(ss.notna(), "-")
        rgt.markdown("**Like for like: share alerted by sex, same number of warning signs**")
        rgt.dataframe(ss, hide_index=True, use_container_width=True)
        rgt.markdown("**Edge cases on one real patient**")
        rgt.dataframe(pd.DataFrame(stt["edge_cases"])[["case", "risk", "level", "rule_checks"]].rename(
            columns={"case": "Case", "risk": "Risk", "level": "Level", "rule_checks": "Rule checks fired"}), hide_index=True, use_container_width=True)
        l.markdown("**Real vs simulated vital signs**")
        rl = pd.DataFrame(stt["realism"])
        rl.columns = ["Signal", "Real ICU patients", "Simulated cohort"]
        l.dataframe(rl, hide_index=True, use_container_width=True)
        l.caption("Real hospital patients breathe faster and often get extra oxygen, so their SpO2 reads higher than the simulated home cohort.")
        st.markdown(f"""<div class='card'><b>What we learned</b><ul style='margin:0.3rem 0 0 0'>
        <li>The twin ran on every real patient with enough data, with no crash and no impossible output, including a missing oxygen sensor.</li>
        <li>Risk rises with real deterioration (rank correlation {stt['spearman_risk_vs_worsening_signs']}). Age 18 vs 90 and switching sex change risk very little; sex is not a model input.</li>
        <li>With the same number of warning signs, women were alerted somewhat more often than men; groups are small (5 to 19 people), so this needs a larger real cohort.</li>
        <li>An oxygen drop alone barely moves the learned risk; the rule layer still flags it as urgent. A clinical version should weight SpO2 more.</li>
        <li>Risk did not predict later in-hospital death (AUROC {stt['auroc_risk_for_later_in_hospital_death']}); death in intensive care is a different event from a COPD flare-up at home.</li>
        </ul></div>""", unsafe_allow_html=True)

    st.markdown("### Real-data check: MIMIC-IV demo vs our synthetic cohort")
    mimic = pd.read_csv(OUTPUTS / "mimic_demo_check.csv")
    st.dataframe(mimic[mimic.measure != "Mean age"], hide_index=True, use_container_width=True)
    st.markdown("### Data sources")
    st.dataframe(pd.DataFrame([
        ["Health records", "Synthea COPD cohort (synthetic) + India overlay (synthetic, ours)", "Apache 2.0 / public domain"],
        ["Real hospital check", "MIMIC-IV Clinical Database Demo v2.2, 100 de-identified patients", "ODbL 1.0"],
        ["Real-patient stress test", "MIMIC-III Clinical Database Demo v1.4, 100 de-identified ICU patients", "ODbL 1.0"],
        ["Air quality", "CPCB daily city data via Kaggle 'Air Quality Data in India (2015-2020)'", "CC0"],
        ["Weather", "Open-Meteo historical weather archive", "CC BY 4.0"],
        ["Watch readings and flare-ups", "Simulated, calibrated to published studies", "Ours"],
    ], columns=["Stream", "Source", "Licence"]), hide_index=True, use_container_width=True)
    st.markdown("### Every simulation setting and its source")
    st.dataframe(pd.DataFrame([[k, str(v["value"]), v["source"]] for k, v in CALIBRATION.items()], columns=["Setting", "Value", "Source"]),
                 hide_index=True, use_container_width=True)
