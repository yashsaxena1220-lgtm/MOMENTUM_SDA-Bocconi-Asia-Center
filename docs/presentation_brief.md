# Presentation brief: BreatheTwin (Team MOMENTUM)

Paste or upload this file into a new chat and ask: "Make a presentation deck from this brief."
All numbers below are current as of 15 Oct 2026.

## Competition and deliverable
- Digital Twin Challenge 2026 by Happiest Health (on Unstop). Submission closes 20 Oct 2026, 7 PM IST.
- Brief: a proof-of-concept digital twin for one chronic condition common in India. It must combine static health records (EHR) with dynamic wearable/IoT time series, predict an adverse event, and show a doctor-facing dashboard. Only anonymised, open-source or synthetic data.
- The submission needs a presentation (PDF or PPT) and a separate architecture diagram (PDF or PPT), plus a 15-20 min demo video.
- Team: MOMENTUM. Anushka Tomar (team leader) and Yash Saxena, SDA Bocconi Asia Center, Mumbai (MBA, IMB9, Class of 2026-28).
- Neither team member codes: keep the slides in plain language.

## Writing style for the deck
Plain, direct, no em dashes, no inflated claims. Always say clearly that patients, wearable readings and flare-ups are simulated, while air quality and weather are real.

## One-line pitch
BreatheTwin is a digital twin of a COPD patient. It learns the patient's own normal, watches their city's air pollution and weather, and warns 1 to 3 days before a likely flare-up, with the reasons and what would lower the risk.

## The problem
- COPD (chronic obstructive pulmonary disease) is a long-term lung disease. India carries one of the largest COPD burdens in the world, driven by smoking (including bidis), household cooking smoke (wood, dung, kerosene) and city air pollution.
- The most harmful moments are flare-ups (exacerbations): a few days when breathing suddenly worsens. They cause hospital admissions, permanent loss of lung function, and deaths.
- Flare-ups are usually caught after the patient is already struggling. The body gives small warning signs days earlier (faster breathing, slightly lower oxygen, higher resting heart rate, less walking, more rescue-inhaler use), but these are too small for families to notice.

## Healthcare use case
Early warning and prevention of COPD flare-ups for Indian patients, used by doctors and health workers watching many patients, and by families through a printable summary and plain advice.

## How it works (for the architecture slide)
Three data streams feed one twin per patient:
1. Health record (static EHR): 400 synthetic COPD patients. 300 come from Synthea (open-source synthetic hospital records; ages 52-92). 100 younger patients (ages 30-51) were added by us, because COPD starts earlier in India. India-specific fields added by us: city, cooking smoke, bidi vs cigarette, blood eosinophils, alpha-1 gene variant, flu vaccine, previous flare-ups.
2. Wearables and smart inhaler (daily): heart rate, breathing rate, blood oxygen (SpO2), steps, sleep, rescue-inhaler puffs, daily-inhaler doses. Simulated, with every effect size taken from published studies (listed in src/config.py).
3. City air and weather (real): CPCB daily PM2.5 for 8 cities (Delhi, Lucknow, Patna, Kolkata, Mumbai, Hyderabad, Bengaluru, Chennai) and Open-Meteo temperature and humidity, replaying 1 Mar 2019 to 29 Feb 2020.

Then:
- Personal baseline: each reading is compared with the patient's OWN normal from the past month, not a textbook range.
- Hybrid risk engine: a LightGBM machine-learning model learns from body signals, inhaler use, weather and the health record. Air pollution is not learned; it uses a published dose-response (DeVries 2017: +2.5% risk per 10 µg/m³ PM2.5). Built-in rules make sure warning signs never lower the risk and taking more inhaler doses never raises it.
- Outputs: the risk of a flare-up in the next 3 days, the reasons, safety checks, what-if answers, smog warnings, and a printable visit summary.

## Results (tested on 120 patients the model never saw; simulated data)
- Accuracy score (AUROC): 0.80. Published real-world COPD tools range from 0.68 to 0.85.
- Flare-ups warned 1 to 3 days ahead: 66%.
- False alerts: 0.80 per patient per month (fewer than one a month).
- What each data stream adds (AUROC): health record alone 0.66, environment alone 0.45, wearables alone 0.79, wearables + health record 0.81, all three 0.80.
- Honest reading: the body signals carry the 3-day warning, and the health record sets each person's starting risk. The environment says little about which exact 3 days, but it explains seasonal risk and powers the smog warnings and what-if advice.
- Share of the twin's reasoning: health record 32%, blood oxygen 15%, breathing rate 12%, rescue inhaler 11%, heart rate 10%, cold snaps 6%, activity 5%, missed doses 3%, air pollution 2%, humidity 2%, sleep 2%.
- Ready-made charts: outputs/model_performance.png and outputs/trigger_importance.png (both current).

## Dashboard features (one slide each, or a features overview)
1. Overview: all patients. Who to call today, ranked by risk, with the main reason and key health-record facts. India map of risk and air. Filter by age group (30-44, 45-59, 60-74, 75+). Smog and cold warnings for the next 3 days.
2. One patient in detail. Risk dial, today's readings against own normal, safety checks, what would lower the risk, full health record (EHR) section, what is pushing risk up or down, 90-day risk history, next-3-days advice for their city, and a downloadable one-page visit summary.
3. What-if lab. Sliders and ready-made scenarios (smog week, cold snap, stopped inhaler, early warning signs, perfect week). Also health-record what-ifs such as age, eosinophils, other conditions, smoking, cooking smoke and flu vaccine.
4. Check a new person. Enter the record plus usual and current readings, and optionally today's PM2.5 from an AQI app. Get an instant risk check with a table of every value the twin used.
5. How it works. Accuracy, data sources and licences, every simulation setting with its source, and a real-data check against MIMIC-IV.
6. Smog is coming warnings. Example: "Patna: air expected to be very poor on Wednesday, Thursday, Friday (PM2.5 up to 202 µg/m³)", with advice (stay indoors, N95 mask, keep inhaler handy, avoid other smoke at home) and "about 49% higher flare-up risk over the following week than on a clean-air day".
7. Visit summary for the doctor. One printable page: readings vs own normal, inhaler use, flare-ups and whether the twin warned before them, air quality, questions to ask the doctor, and when to get help now.

Plain-language design: every page has a "How to read this page" box, risk levels with meanings (Low: no action; Medium: watch closely; High: contact the patient today), and a "Medical words explained" glossary.

## Why it matters
- 1 to 3 days of warning is enough to start medicines early, see a doctor, or avoid a trigger: a phone call instead of a hospital stay.
- It compares each person with themselves, so small changes become meaningful.
- It explains its reasons, so doctors and families can act.
- It links health to India's air and seasons, and turns forecasts into practical advice.
- One doctor or health worker can watch many patients and focus on the few most at risk.

## Real-data check
The health-record code runs on the real MIMIC-IV demo (ODbL licence): 14 COPD patients, aggregate comparison only. Sex mix and heart disease match well. Heart failure (57% real vs 2% ours) and diabetes (64% vs 18%) do not, which is a known limit of synthetic records.

## Data sources and licences
| Stream | Source | Licence |
|---|---|---|
| Health records | Synthea COPD cohort (synthetic) + India overlay and younger patients (synthetic, ours) | Apache 2.0 |
| Real-data check | MIMIC-IV Clinical Database Demo v2.2 | ODbL 1.0 |
| Air quality | CPCB daily city data via Kaggle "Air Quality Data in India (2015-2020)" | CC0 |
| Weather | Open-Meteo historical weather archive | CC BY 4.0 |
| Wearables and flare-ups | Simulated, calibrated to published studies | Ours |

## Tech stack
Python, pandas, LightGBM, scikit-learn, Plotly, Streamlit (dashboard), matplotlib. Synthea (Java) for the synthetic records.

## Honest limitations (include a slide)
- Patients, wearable readings and flare-ups are simulated, so the accuracy shows the idea works, not clinical accuracy.
- No India-specific PM2.5-to-COPD effect size was found; the 2.5% per 10 µg/m³ figure is global.
- Some effects are our own assumptions and are labelled so (cooking smoke, age, other conditions, low BMI, humidity, missed doses).
- The demo "forecast" replays real 2019-20 data; a live version would use an air-quality forecast service.
- It currently needs a smartwatch or pulse oximeter for daily readings.

## Next steps (roadmap slide)
- Validate on real Indian patients with a hospital partner.
- A "My lungs today" page for patients and families, with a daily symptom check-in that works with just a phone and a low-cost pulse oximeter.
- Live air-quality forecasts, SMS/WhatsApp alerts, Hindi and regional languages.
- Fairness checks across age, sex, city and severity.

## Suggested deck outline (about 12-14 slides)
1. Title: BreatheTwin, team, college
2. The problem: COPD in India and flare-ups
3. The insight: warning signs appear days earlier
4. Our solution: what BreatheTwin does, in one picture
5. How it works: three data streams into one twin (architecture)
6. The model: personal baseline + hybrid risk engine
7. Results: accuracy, warnings ahead, false alerts, vs published range
8. What each data stream adds
9. Dashboard walkthrough (3-4 screenshots)
10. Smog warnings and visit summary
11. Who it helps and why it matters
12. Data, licences and honesty about simulation
13. Limitations and next steps
14. Thank you / links (GitHub, demo video)

## Images available
- outputs/model_performance.png, outputs/trigger_importance.png: current.
- docs/screenshots/*.png: OLD (taken before the 13-15 Oct changes). Retake from the live dashboard before using: overview, one patient (with the health-record section), what-if lab, check a new person, smog warnings, and a visit summary.
