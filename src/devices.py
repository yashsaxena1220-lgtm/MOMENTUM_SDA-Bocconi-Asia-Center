"""
Which wearables and IoT devices BreatheTwin can take readings from, and which sensor gives which signal.

One source of truth for the dashboard's "Devices and sensors" page, the README and the presentation.
In this prototype the watch, oximeter and inhaler readings are simulated (or typed in on the "Check a new person"
page); the device connections listed here are the integration plan, using each platform's published data API.
"""

# Every signal the twin reads, the sensor that measures it, and where it enters the model.
SIGNALS = [
    # signal, sensor, device(s), how often, used by the twin as
    ("Resting heart rate", "Optical heart-rate sensor (green-light PPG) on the wrist or finger",
     "Smartwatch or fitness band; pulse oximeter", "Daily resting value", "Change vs own normal (heart-rate group)"),
    ("Breathing rate", "PPG + motion sensor, measured during sleep",
     "Smartwatch or band (Fitbit, Apple Watch, Galaxy Watch, Garmin)", "Nightly average", "Change vs own normal (breathing group)"),
    ("Blood oxygen (SpO2)", "Red and infrared light sensor (pulse oximetry)",
     "Fingertip or ring pulse oximeter; many smartwatches", "Morning spot check or overnight", "Change vs own normal; urgent check below 90%"),
    ("Steps / activity", "3-axis accelerometer",
     "Smartwatch, band or the phone itself", "Daily total", "Change vs own normal (activity group)"),
    ("Sleep hours", "Accelerometer + heart-rate pattern",
     "Smartwatch or band", "Nightly", "Change vs own normal (sleep group)"),
    ("Rescue inhaler puffs", "Actuation sensor in a clip-on inhaler add-on (Bluetooth)",
     "Smart inhaler add-on, or one tap in the app", "Every puff, with time", "Puffs vs own normal (rescue group)"),
    ("Controller doses taken", "Same clip-on sensor on the daily controller inhaler",
     "Smart inhaler add-on, or one tap in the app", "Every dose", "Share of doses taken in 7 days (adherence group)"),
    ("Blood pressure", "Cuff pressure sensor (oscillometric)",
     "Bluetooth BP monitor", "Weekly or when unwell", "Shown to the doctor; not yet a risk input"),
    ("Outdoor PM2.5 / AQI", "Government air-quality monitoring stations (CPCB CAAQMS)",
     "City sensor network, read by API (no device for the patient)", "Daily", "Published dose-response x model risk; smog warnings"),
    ("Temperature and humidity", "Weather stations and reanalysis (Open-Meteo)",
     "Weather API (no device for the patient)", "Daily", "Cold-snap and humid-heat groups; cold warnings"),
]

# Compatible devices, what each one gives the twin, and how the data reaches it.
DEVICES = [
    # category, examples, signals given, how data reaches BreatheTwin, cost tier, note
    ("Smartwatch / fitness band", "Fitbit Charge 6, Sense, Versa", "Heart rate, breathing rate (sleep), SpO2 (sleep), steps, sleep",
     "Fitbit Web API (breathing-rate and SpO2 endpoints)", "Mid", "Most complete single device for the twin"),
    ("Smartwatch", "Apple Watch (Series 6 or later)", "Heart rate, respiratory rate (sleep), SpO2, steps, sleep",
     "Apple HealthKit on the patient's iPhone", "Premium", ""),
    ("Smartwatch", "Samsung Galaxy Watch (4 or later)", "Heart rate, SpO2, respiratory rate (sleep), steps, sleep",
     "Samsung Health to Android Health Connect", "Mid-premium", ""),
    ("Smartwatch", "Garmin (Venu, Forerunner, vivosmart)", "Heart rate, respiration, Pulse Ox, steps, sleep",
     "Garmin Health API or Health Connect", "Mid-premium", ""),
    ("Budget smartwatch", "Noise, boAt, Fire-Boltt, Amazfit", "Heart rate, SpO2 spot check, steps, sleep (breathing rate on some models)",
     "Health Connect where the brand's app syncs to it; otherwise typed in", "Low", "Check the app syncs to Health Connect"),
    ("Fingertip pulse oximeter", "Any CE/CDSCO-approved model; Bluetooth models sync", "SpO2, pulse",
     "Bluetooth to the app, or the family types the number in", "Low", "Minimum kit with any watch"),
    ("Ring oximeter", "Wellue O2Ring", "Overnight SpO2, pulse",
     "Vendor app export / Bluetooth", "Mid", "Catches night-time oxygen dips"),
    ("Smart inhaler add-on", "ADHERO (Lupin + Aptar, India), Propeller Health, Adherium Hailie", "Rescue puffs, controller doses, time of use",
     "Vendor app / API; one-tap logging as fallback", "Mid", "ADHERO is the India-launched option"),
    ("Bluetooth BP monitor", "Omron with OMRON connect", "Blood pressure, pulse",
     "OMRON connect app to Health Connect / HealthKit", "Low-mid", ""),
    ("Phone", "Any Android or iPhone", "Steps; acts as the Bluetooth gateway and alert screen",
     "Health Connect / HealthKit", "Already owned", "Works with no watch for steps only"),
    ("City air network", "CPCB continuous ambient air-quality stations", "PM2.5, AQI",
     "CPCB / data.gov.in feed (real data in this prototype)", "Free", "Real in the prototype"),
    ("Weather service", "Open-Meteo", "Temperature, night low, humidity",
     "Open-Meteo API (real data in this prototype)", "Free", "Real in the prototype"),
]

KITS = [
    ("Minimum kit", "Any smartwatch or band that syncs to Health Connect or Apple Health + a fingertip pulse oximeter",
     "Heart rate, breathing rate, SpO2, steps, sleep. Inhaler use typed in with one tap."),
    ("Full kit", "Minimum kit + smart inhaler add-on (e.g. ADHERO) + Bluetooth BP monitor",
     "Adds automatic rescue and controller inhaler tracking, and blood pressure for the doctor."),
    ("No-watch kit", "Phone + fingertip pulse oximeter, readings typed in each morning",
     "SpO2, pulse and steps; breathing rate counted by the family for 30 seconds. Lower accuracy, near-zero cost."),
]
