"""
Central settings for the COPD Digital Twin.

Every number that shapes the simulated wearable stream or the flare-up events
lives in CALIBRATION, with the study it comes from. Numbers marked ASSUMPTION
have no published source we could find and are our own design choice.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
OUTPUTS = ROOT / "outputs"

SEED = 2026

# Monitoring window: one full year of seasons, ending before the COVID-19 lockdown
# (March 2020) changed pollution levels across India.
START_DATE = "2019-03-01"
END_DATE = "2020-02-29"

# Training cities: different climates and different main triggers.
# share = fraction of synthetic patients assigned to the city.
CITIES = {
    "Delhi":     {"lat": 28.61, "lon": 77.21, "region": "North (Indo-Gangetic plain)", "share": 0.18},
    "Lucknow":   {"lat": 26.85, "lon": 80.95, "region": "North (Indo-Gangetic plain)", "share": 0.12},
    "Patna":     {"lat": 25.59, "lon": 85.14, "region": "East (Indo-Gangetic plain)",  "share": 0.10},
    "Kolkata":   {"lat": 22.57, "lon": 88.36, "region": "East (coastal delta)",        "share": 0.13},
    "Mumbai":    {"lat": 19.08, "lon": 72.88, "region": "West (coastal)",              "share": 0.14},
    "Hyderabad": {"lat": 17.39, "lon": 78.49, "region": "South (Deccan plateau)",      "share": 0.11},
    "Bengaluru": {"lat": 12.97, "lon": 77.59, "region": "South (plateau)",             "share": 0.11},
    "Chennai":   {"lat": 13.08, "lon": 80.27, "region": "South (coastal)",             "share": 0.11},
}

# Cohort balance. Synthea's COPD module only produces patients aged 52-92 and mostly GOLD 4, so we
# (1) rank Synthea patients by their lung-function value and assign stages in typical clinic shares, and
# (2) add younger synthetic patients (India overlay) so every adult generation is represented.
GOLD_SHARES = {1: 0.15, 2: 0.42, 3: 0.30, 4: 0.13}          # ASSUMPTION: typical clinic mix (GOLD 2 most common)
YOUNG_COHORT = {"age_bands": {(30, 39): 40, (40, 51): 60}}   # ASSUMPTION; COPD is rare below 30

# Synthea's COPD module diagnosis codes (SNOMED CT)
COPD_SNOMED = {"87433001": "Pulmonary emphysema", "185086009": "Chronic obstructive bronchitis"}
COPD_ICD_PREFIXES = ("491", "492", "496", "J44")   # used for the MIMIC-IV demo

CALIBRATION = {
    # ---- how often flare-ups happen
    "exac_rate_per_year_by_stage": {
        "value": {1: 0.50, 2: 0.85, 3: 1.34, 4: 2.00},
        "source": "Hurst et al., NEJM 2010 (ECLIPSE), first-year rates for GOLD 2/3/4. "
                  "GOLD 1 = ASSUMPTION (ECLIPSE did not enrol GOLD 1).",
    },
    "frequent_exacerbator_share_by_stage": {
        "value": {1: 0.15, 2: 0.22, 3: 0.33, 4: 0.47},
        "source": "Hurst et al., NEJM 2010 (ECLIPSE): >=2 events/yr in 22%, 33%, 47% of GOLD 2/3/4. "
                  "GOLD 1 = ASSUMPTION.",
    },
    "frequent_exacerbator_rate_multiplier": {
        "value": 1.8,
        "source": "ASSUMPTION, chosen so prior flare-ups are the strongest single predictor, as ECLIPSE reports.",
    },
    "event_duration_days": {
        "value": {"median": 5, "log_sd": 0.8},
        "source": "Shah et al., JMIR 2017: mean 8.8 days, median 4. Lognormal approximation.",
    },
    "prodrome_days": {
        "value": (5, 7),
        "source": "Five to seven days of warning signs: Yanez 2012, Hurst 2010, Shah 2017.",
    },
    "silent_event_share": {
        "value": 0.30,
        "source": "Yanez et al. 2012: only 21 of 30 hospitalised patients showed the breathing-rate rise.",
    },
    # ---- what the warning signs look like (change from the patient's own normal)
    "resp_rate_rise": {
        "value": {"day_minus_2": 2.3, "day_minus_1": 4.4, "onset": 4.4},
        "source": "Yanez et al., Respir Med 2012 (PubMed 22797131).",
    },
    "heart_rate_rise": {
        "value": {"prodrome_week": 3.0, "onset": 6.5},
        "source": "Hurst et al. 2010 (PMC2978135); Shah et al., JMIR 2017.",
    },
    "spo2_drop": {
        "value": {"prodrome_week": 1.0, "onset": 1.5},
        "source": "Hurst et al. 2010; Shah et al., JMIR 2017.",
    },
    "steps_drop_per_day": {
        "value": {"prodrome": 200, "during": 480},
        "source": "During: Alahmari et al. 2014 (about -480/day in first week). Prodrome value = ASSUMPTION.",
    },
    "daily_noise_sd": {
        "value": {"heart_rate": 4.9, "spo2": 1.0, "resp_rate": 1.2, "steps_cv": 0.30},
        "source": "Heart rate and SpO2 day-to-day SD: Hurst 2010 / Shah 2017. Breathing rate and steps = ASSUMPTION.",
    },
    # ---- environmental triggers
    "pm25_effect": {
        "value": {"pct_per_10ug": 2.5, "reference_ug": 40, "cap_ug": 300, "window_days": 7, "lag_start": 2},
        "source": "DeVries et al. 2017 meta-analysis: +2.5% COPD visits/admissions per 10 µg/m³ PM2.5 (global). "
                  "No India-specific estimate found. Rolling lag 2-7 days and cap at 300 µg/m³ = ASSUMPTION.",
    },
    "temperature_drop_effect": {
        "value": {"drop_c": 6.0, "cum_rr_21d": 1.79, "lag_days": 21},
        "source": "Fu et al., Front Public Health 2023 (Beijing): day-to-day mean temperature drop of 6 C, "
                  "21-day cumulative RR 1.79 (95% CI 1.08-2.96). Applied linearly per degree of drop = ASSUMPTION.",
    },
    "humid_heat_effect": {
        "value": {"rh_threshold": 80, "temp_threshold": 28, "multiplier": 1.15},
        "source": "ASSUMPTION. No published effect size found; humidity was only a control variable in Fu 2023.",
    },
    "missed_dose_effect": {
        "value": {"multiplier_at_zero_adherence": 1.6},
        "source": "ASSUMPTION. Direction supported by GOLD maintenance-therapy guidance; size not sourced.",
    },
    "flu_vaccine_effect": {
        "value": {"multiplier": 0.85},
        "source": "ASSUMPTION (GOLD recommends influenza vaccination to reduce exacerbations).",
    },
    # ---- health-record factors (each multiplies the patient's yearly flare-up rate; the cohort is then
    #      rescaled so each GOLD stage's average rate still matches ECLIPSE)
    "eosinophil_effect": {
        "value": {"low_ul": 150, "high_ul": 340, "multiplier_at_high": 1.76},
        "source": "Vedel-Krogh et al., AJRCCM 2016 (Copenhagen General Population Study): eosinophils >=340 cells/µL, "
                  "adjusted IRR 1.76 for severe exacerbations. Smooth rise from 150 to 340 = ASSUMPTION.",
    },
    "current_smoking_effect": {
        "value": {"multiplier": 1.28},
        "source": "Au et al., J Gen Intern Med 2009: quitting lowered exacerbation risk (adjusted HR 0.78), "
                  "so current vs former smoker = 1/0.78.",
    },
    "biomass_effect": {
        "value": {"multiplier": 1.2},
        "source": "ASSUMPTION. Household biomass smoke is a major COPD cause in India (Salvi & Barnes, Lancet 2009); "
                  "no published effect size on flare-up rate found.",
    },
    "age_effect": {
        "value": {"per_decade": 1.10, "reference_age": 65},
        "source": "ASSUMPTION. Older age is linked to more frequent flare-ups; size not sourced.",
    },
    "comorbidity_effect": {
        "value": {"per_condition": 1.10},
        "source": "ASSUMPTION. Heart disease, diabetes and anaemia are linked to more flare-ups; size not sourced.",
    },
    "low_bmi_effect": {
        "value": {"bmi_below": 18.5, "multiplier": 1.25},
        "source": "ASSUMPTION. Low BMI marks a poorer outlook in COPD (BODE index, Celli et al., NEJM 2004); size not sourced.",
    },
    "indoor_pm_fraction_with_purifier": {
        "value": 0.55,
        "source": "ASSUMPTION used only by the what-if tool.",
    },
}


def cal(key):
    """Shortcut: calibration value."""
    return CALIBRATION[key]["value"]
