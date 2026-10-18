"""
Draw the functioning flowchart of BreatheTwin (used in the README, the dashboard and the presentation).

Output: docs/flowchart.png and docs/flowchart.pdf
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

from config import ROOT

NAVY, TEAL, INK, MUTED, LINE = "#12303F", "#1F5F7A", "#1B2A35", "#536673", "#C9D6DE"
FILL = {"input": "#EAF3F6", "step": "#FFFFFF", "engine": "#E3EEF2", "out": "#F3F0E8", "act": "#E9F1EC"}
EDGE = {"input": TEAL, "step": "#7C97A6", "engine": NAVY, "out": "#8C7B55", "act": "#3C7A5E"}

W, H = 16.2, 10.6
fig = plt.figure(figsize=(W, H), dpi=150)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")


def box(x, y, w, h, title, body="", kind="step", tsize=12.5, bsize=9.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.14",
                                fc=FILL[kind], ec=EDGE[kind], lw=1.6))
    ty = y + h - 0.32 if body else y + h / 2
    ax.text(x + w / 2, ty, title, ha="center", va="center" if not body else "top", fontsize=tsize,
            fontweight="bold", color=INK, family="DejaVu Sans")
    if body:
        ax.text(x + w / 2, y + h - 0.72, body, ha="center", va="top", fontsize=bsize, color=MUTED,
                linespacing=1.35, family="DejaVu Sans")
    return (x, y, w, h)


def arrow(x1, y1, x2, y2, label="", color="#5F7884", lw=1.6, ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>,head_length=0.6,head_width=0.32", color=color, lw=lw, ls=ls,
                                shrinkA=0, shrinkB=0))
    if label:
        ax.text((x1 + x2) / 2 + 0.08, (y1 + y2) / 2, label, fontsize=8.8, color=MUTED, va="center", ha="left")


def stage(y, text):
    ax.text(0.25, y, text, fontsize=9, color=TEAL, fontweight="bold", va="center", rotation=90)


ax.text(W / 2, H - 0.35, "BreatheTwin: how the COPD digital twin works, every morning", ha="center", va="center",
        fontsize=17, fontweight="bold", color=NAVY, family="DejaVu Serif")

# 1. inputs
y1, h1 = 8.3, 1.62
stage(y1 + h1 / 2, "1  COLLECT")
a = box(0.7, y1, 4.7, h1, "Wearables and home IoT",
        "Smartwatch: heart rate, breathing rate,\nsteps, sleep\nPulse oximeter: SpO2\nSmart inhaler: rescue puffs, doses", "input")
b = box(5.75, y1, 4.5, h1, "Health record (EHR)",
        "Age, GOLD stage, past flare-ups,\nsmoking, cooking smoke, eosinophils,\nother conditions, BMI, flu vaccine,\nhome oxygen", "input")
c = box(10.6, y1, 4.7, h1, "City air and weather (real)",
        "PM2.5 and AQI from CPCB stations\nTemperature, night low, humidity\nfrom Open-Meteo\nCity matched to the patient", "input")

# 2. ingest
y2, h2 = 6.9, 0.95
stage(y2 + h2 / 2, "2  CLEAN")
d = box(0.7, y2, 14.6, h2, "Daily summary per patient",
        "Phone app / Health Connect / HealthKit / APIs  →  one row per day  →  unit and range checks, missing sensor kept as missing (never zero)",
        "step", bsize=9.8)
for bx in (a, b, c):
    arrow(bx[0] + bx[2] / 2, y1, bx[0] + bx[2] / 2, y2 + h2)

# 3. twin
y3, h3 = 5.1, 1.32
stage(y3 + h3 / 2, "3  TWIN")
e = box(0.7, y3, 6.2, h3, "Personal baseline (the twin)",
        "Own normal = median of days t-28 to t-8\nToday and 3-day change vs own normal, in own spread", "engine")
f = box(7.3, y3, 4.2, h3, "Hybrid risk engine",
        "LightGBM on body, inhaler,\nweather, record  ×  published\nPM2.5 dose-response", "engine")
g = box(11.9, y3, 3.4, h3, "Rule checks",
        "Breathing +3/min, SpO2 -2 pts,\nHR +7 bpm vs own normal;\nSpO2 below 90% = urgent", "engine")
arrow(3.8, y2, 3.8, y3 + h3)
arrow(13.6, y2, 13.6, y3 + h3)
arrow(6.9, y3 + h3 / 2, 7.3, y3 + h3 / 2)

# 4. decide
y4 = 3.72
stage(y4, "4  DECIDE")
cx, cy, dw, dh = 9.4, y4, 2.0, 0.62
ax.add_patch(Polygon([(cx, cy + dh), (cx + dw, cy), (cx, cy - dh), (cx - dw, cy)], closed=True, fc="#FFF8EC", ec="#C98A1B", lw=1.6))
ax.text(cx, cy, "Flare-up risk in\nnext 1-3 days?", ha="center", va="center", fontsize=10.5, fontweight="bold", color=INK)
arrow(9.4, y3, 9.4, cy + dh)
arrow(13.6, y3, 10.6, cy + 0.32)
for txt, x, col in [("High: call patient today", 0.7, "#B23A2E"), ("Medium: watch closely", 3.95, "#C98A1B"), ("Low: no action", 13.2, "#5B8A72")]:
    w = 3.0 if x < 10 else 2.1
    ax.add_patch(FancyBboxPatch((x, cy - 0.32), w, 0.64, boxstyle="round,pad=0.02,rounding_size=0.3", fc=col, ec=col))
    ax.text(x + w / 2, cy, txt, ha="center", va="center", fontsize=9.6, color="white", fontweight="bold")
arrow(cx - dw, cy, 6.95, cy)
arrow(cx + dw, cy, 13.2, cy)

# 5. outputs
y5, h5 = 1.0, 1.3
stage(y5 + h5 / 2, "5  ACT")
outs = [("Ranked call list", "Who to phone today,\nmain reason, record facts"),
        ("Why: reasons", "SHAP push of each trigger\nin plain language"),
        ("What would help", "What-if: purifier, every dose,\nstay indoors"),
        ("Smog and cold alerts", "Next 3 days per city,\nwith advice"),
        ("Visit summary", "One printable page for\nthe family and doctor")]
ow, gap = 2.72, 0.25
for i, (t, s) in enumerate(outs):
    x = 0.7 + i * (ow + gap)
    box(x, y5, ow, h5, t, s, "out", tsize=11, bsize=9)
arrow(2.2, cy - 0.32, 2.2, y5 + h5)

ax.add_patch(FancyBboxPatch((0.7, 0.2), 14.6, 0.5, boxstyle="round,pad=0.02,rounding_size=0.14", fc=FILL["act"], ec=EDGE["act"], lw=1.4))
ax.text(8.0, 0.45, "Doctor, nurse or ASHA worker phones the patient or adjusts treatment  →  outcome recorded  →  baseline updates the next day",
        ha="center", va="center", fontsize=10, color=INK, fontweight="bold")
# feedback loop
ax.plot([15.3, 15.65, 15.65], [0.45, 0.45, y2 + h2 / 2], color=EDGE["act"], lw=1.5, ls="--")
arrow(15.65, y2 + h2 / 2, 15.3, y2 + h2 / 2, color=EDGE["act"])
ax.text(15.8, 3.7, "feedback loop", rotation=90, fontsize=8.5, color=EDGE["act"], va="center", ha="center")

out = ROOT / "docs"
fig.savefig(out / "flowchart.png", dpi=150, facecolor="white")
fig.savefig(out / "flowchart.pdf", facecolor="white")
print("wrote", out / "flowchart.png")
