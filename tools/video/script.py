"""BreatheTwin demo video, v2: livelier narration, user's deck, live test of a new patient.

Each part has a visual: ("slides", [slide numbers]) or ("app", start_url). Slide 90 = the flowchart image.
Each line: (speaker, text, actions[, pace]) - actions run when the line starts (app parts only).
pace: optional speed for that line (default per speaker).
"""
BASE = "http://localhost:8501/?"

PARTS = [
 ("1. Opening and team", ("slides", [1]), [
  ("A", "Imagine a 68-year-old man in Delhi. It's early November. The smog has been bad for a week, and the nights are getting colder.", [], 0.95),
  ("A", "His breathing is a little faster than usual. His oxygen is a point lower. He's reaching for his blue inhaler more often. None of it feels serious.", [], 0.95),
  ("A", "Three days later, he's in hospital with a COPD flare-up.", [], 0.92),
  ("A", "The warning signs were there. But nobody was watching them, and nobody connected them with the air he was breathing.", []),
  ("A", "Hi! We're team MOMENTUM. I'm Anushka Tomar, the team leader.", []),
  ("Y", "And I'm Yash Saxena. We're both MBA students at SDA Bocconi Asia Center in Mumbai.", []),
  ("A", "This is BreatheTwin: a digital twin of a COPD patient. It learns each person's own normal, watches their city's air and weather, and warns one to three days before a likely flare-up. And it tells you why, and what would lower the risk.", []),
  ("Y", "We'll walk you through the problem, how the twin works, and a live demo. Then we'll be honest about what our results do, and don't, prove.", []),
 ]),
 ("2. The problem", ("slides", [2]), [
  ("A", "So, what is COPD? Chronic obstructive pulmonary disease. It's a long-term lung disease that makes every breath harder. In 2016, India had an estimated 55 million people living with it.", []),
  ("A", "And here's what makes India different. The biggest causes aren't cigarettes. Outdoor air pollution drives about a third of India's COPD burden. Smoke from cooking with wood or dung drives another quarter. Both count for more than smoking.", []),
  ("A", "The most dangerous moment is the flare-up: a few days when breathing suddenly gets much worse. Flare-ups put people in hospital, and each one can leave the lungs permanently weaker.", []),
  ("A", "But here's the hopeful part. The body gives warning signs. Breathing rises by about two breaths a minute two days before a flare-up, and about four the day before. Oxygen dips. Heart rate climbs. People walk less, and use their rescue inhaler more.", []),
  ("A", "The trouble is, these changes are tiny. A family won't notice them, and nobody tracks them between clinic visits. Nobody links them to the smog, either. In the year we replay, Delhi's PM2.5 averaged 104. That's about seven times the WHO safe level.", []),
  ("A", "So the opportunity is clear. Let's use the days of warning the body already gives us.", [], 0.95),
 ]),
 ("3. How the twin works", ("slides", [4, 90]), [
  ("Y", "So how does it work? BreatheTwin brings together three streams of data for every patient.", []),
  ("Y", "One: the health record. Age, how severe the COPD is, past flare-ups, smoking, cooking smoke at home, blood tests. That sets each person's starting risk.", []),
  ("Y", "Two: daily readings from devices people can already buy. A smartwatch, a fingertip pulse oximeter, and a clip-on sensor for the inhaler.", []),
  ("Y", "Three: the city's air quality and weather. And this part is real data, from CPCB monitoring stations in eight Indian cities, and Open-Meteo weather.", []),
  ("Y", "Every morning, the twin compares today with the patient's own normal from the past month. Not a textbook range. Their normal. Because a breathing rate of 18 can be fine for one person, and a warning sign for another.", [("slide", 90)]),
  ("Y", "The risk engine is a hybrid. A machine-learning model, LightGBM, learns the patterns in the body signals and the record. For air pollution, we don't let the model guess. We use the effect from a published meta-analysis: about 2.5 percent more risk for every 10 micrograms of PM2.5.", []),
  ("Y", "Then it decides. High: call the patient today. Medium: watch closely. Low: no action. And on top sits a safety rule. If oxygen falls below 90 percent, the patient is Urgent, whatever the model says. We'll show you that in a minute.", []),
 ]),
 ("4. Demo: the doctor's overview", ("app", BASE + "page=Command%20centre&day=2019-11-05"), [
  ("A", "Okay, let's open the dashboard. This is what a doctor or a community health worker sees each morning. We're replaying a real year of Indian air and weather, and today is the 5th of November, 2019. Winter smog is just starting.", [("hl", "Overview: all patients")]),
  ("A", "Every page starts with a short guide, because we wrote this for people without medical training too.", [("hl", "How to read this page")]),
  ("A", "Across 420 patients in eight cities, 18 are high risk today. And Patna has the worst air: PM2.5 of 248. That's very poor.", [("scroll", "High-risk patients"), ("hl", "High-risk patients")]),
  ("A", "The map shows the same picture by city. Bigger bubble, more high-risk patients. The colour is today's air.", [("scroll", "Risk and air across India"), ("hl", "Risk and air across India")]),
  ("A", "But this is the part a doctor will use most: who to call today, ranked by risk. Mohan Gowda, 92, in Lucknow, is at 94 percent. His breathing is 3.3 breaths a minute above his own normal. So before picking up the phone, the doctor already knows why.", [("scroll", "Call these patients today"), ("hl", "Mohan Gowda")]),
  ("A", "You can filter by age. Our patients range from 22 to 92, and every patient under 30 has a known cause of early COPD, like an alpha-1 gene variant, or lung damage after tuberculosis.", [("click", "Under 30")]),
  ("A", "Further down: smog and cold warnings for the next three days. Lucknow, Patna and Delhi expect very poor air this week. So the advice is practical. Keep windows shut. Wear an N95 outdoors. Keep the rescue inhaler close.", [("click", "All ages"), ("scroll", "Smog and cold warnings")]),
  ("A", "And this chart shows why air matters across a season. As pollution climbs into winter, the number of high-risk patients climbs right along with it.", [("scroll", "The year at a glance")]),
 ]),
 ("5. Demo: one patient in detail", ("app", BASE + "page=Patient%20twin&pid=MOM-0009&day=2019-11-05"), [
  ("Y", "Let's open one patient from that list. Vimala Pillai, 91, from Delhi.", [("hl", "Vimala Pillai")]),
  ("Y", "This dial is her chance of a flare-up in the next three days. 46.5 percent. Yesterday, it was under 3. The black mark is the alert line, and she's well past it. The twin's advice: contact her today.", [("scroll", "Flare-up risk, next 3 days")]),
  ("Y", "Why? Look at her readings against her own normal. Breathing: 17.8 breaths a minute, that's 3.4 above her usual. Resting heart rate: 9 beats higher. And she walked about 1,900 steps, against her usual 3,100.", [("hl", "Breathing rate")]),
  ("Y", "These checks are simple rules a doctor can verify at a glance. Breathing up. Heart rate up. And she's taken only 64 percent of her daily inhaler doses this week.", [("hl", "Checks against own normal")]),
  ("Y", "So what would help? Staying indoors with an air purifier brings her risk from 47 down to 40 percent. Taking every inhaler dose barely moves it today, because the warning signs are already there. We'd rather say that honestly than overpromise.", [("hl", "What would lower the risk")]),
  ("Y", "This is her health record, the fixed part of the twin. GOLD stage 2. One flare-up last year. A former bidi smoker. Cooking smoke at home. High eosinophils. Plus diabetes and heart disease. Together, that nearly doubles her risk compared with an average patient.", [("scroll", "Health record (EHR)")]),
  ("Y", "And this chart breaks the risk into its causes. Red pushes it up, green pushes it down. Today, the biggest push is her breathing.", [("scroll", "What is pushing the risk")]),
  ("Y", "Finally, the family can download a one-page visit summary and take it to the doctor. Readings, reasons, and questions to ask.", [("summary",)]),
 ]),
 ("6. Demo: the safety override", ("app", BASE + "page=Patient%20twin&pid=MOM-0302&day=2019-03-27"), [
  ("Y", "Now, a case that shows why the model doesn't get the last word. Sunita Ansari, 30, from Delhi, with severe COPD. It's the 27th of March, 2019.", [("hl", "Sunita Ansari")]),
  ("Y", "The machine-learning model gives her less than 1 percent risk. On its own, that means: do nothing. But look at her oxygen this morning. 89.9 percent. In COPD, below 90 is a red flag.", [("scroll", "Flare-up risk, next 3 days"), ("hl", "Blood oxygen")]),
  ("Y", "So the safety rule steps in. She's marked Urgent, and she goes straight to the top of the doctor's call list, with the reason in plain words.", [("hl", "below 90%")]),
  ("Y", "And honestly? We found this gap ourselves. When we stress-tested the twin on real hospital patients, someone with oxygen at 82 percent still came out Low. We didn't hide it. We fixed it. Rules catch emergencies. The model catches the slow drift before them.", []),
 ]),
 ("7. Demo: the what-if lab", ("app", BASE + "page=Twin%20Lab%20(what-if)&pid=MOM-0009&day=2019-11-05"), [
  ("A", "This is the what-if lab. A doctor, or a worried family member, can ask questions here safely. Nothing changes the real record.", [("hl", "What-if lab")]),
  ("A", "What if Vimala's readings went back to her normal, and she took every dose? Watch the dial. Her risk drops sharply.", [("click", "Perfect week")]),
  ("A", "And what if Delhi had a week of severe smog instead? The risk goes up. That's the published pollution effect at work, not a guess.", [("click", "Reset to today"), ("click", "Smog week")]),
  ("A", "A cold snap pushes it up too.", [("click", "Reset to today"), ("click", "Cold snap")]),
  ("A", "You can change the health record as well. Higher eosinophils, a blood marker, mean more frequent flare-ups. So the risk edges up.", [("click", "Reset to today"), ("click", "Patient record"), ("eos",)]),
  ("A", "These curves change one thing at a time. The dot is where she is today. And they show the rules we built in: warning signs never lower the risk, and taking more inhaler doses never raises it. So every answer moves the way a doctor would expect.", [("scroll", "How risk responds to each lever")]),
 ]),
 ("8. Demo: testing the model on a new patient", ("app", BASE + "page=Add%20a%20patient&day=2019-11-05"), [
  ("Y", "Now let's test the model live, on a patient it has never seen. This page builds a new twin in about a minute.", [("hl", "Check a new person")]),
  ("Y", "Our test patient is a 23-year-old woman in Mumbai. GOLD stage 2. Three flare-ups last year. She's never smoked. Eosinophils of 320, a BMI of 19, and she's on a daily inhaler.",
   [("fill_label", "Name", "Test patient"), ("fill_label", "Age (years)", "23"), ("select", "Sex", "F"), ("select", "City", "Mumbai"),
    ("fill_label", "Flare-ups in the last year", "3"), ("select", "Smoking", "never"), ("fill_label", "Blood eosinophils (cells/µL)", "320"),
    ("fill_label", "BMI (kg/m²)", "19")]),
  ("Y", "Now her readings. Usually, she breathes 14 times a minute, her oxygen is 99 percent, and she walks about 4,000 steps a day. Over the last three days: 18 breaths a minute, oxygen at 97, only a thousand steps, and one extra puff of her rescue inhaler.",
   [("scroll", "2. Readings"), ("fill", "u_hr", "58"), ("fill", "n_hr", "52"), ("fill", "u_rr", "14"), ("fill", "n_rr", "18"),
    ("fill", "u_spo2", "99"), ("fill", "n_spo2", "97"), ("fill", "n_steps", "1000"), ("fill", "u_puffs", "2"), ("fill", "n_puffs", "3"),
    ("fill", "u_sleep", "7"), ("fill", "n_sleep", "6.5")]),
  ("Y", "Honestly, none of those numbers looks alarming on its own. Her oxygen is still 97. So, what does the twin say?", [("submit",), ("scroll", "Test patient, 23 yrs")], 0.97),
  ("Y", "High risk. About a 28 percent chance of a flare-up in the next three days. And it explains why. Her breathing is 4 breaths above her own normal. Her oxygen is 2 points below it. She's hardly walking, and she's using her rescue inhaler more.", [("hl", "Test patient, 23 yrs")]),
  ("Y", "That's the whole point of a personal twin. Compared with a textbook, she looks fine. Compared with herself, she's drifting. The twin also flags that COPD is rare under 30, so a doctor reads the result with care.", [("scroll", "Checks against own normal")]),
  ("Y", "We ran other tests too. Readings at her normal give about 0.3 percent. Strong warning signs give 99. And this table shows every value the twin used, so nothing is hidden.", [("scroll", "What the twin read")]),
 ]),
 ("9. Demo: devices and what the patient sees", ("app", BASE + "page=Devices&day=2019-11-05"), [
  ("A", "So what does the patient actually wear? Nothing unusual. No needle, no blood test, nothing under the skin. Just a smartwatch, a fingertip oximeter, or an inhaler clip.", []),
  ("A", "Here's what they'd see. These are design mock-ups, filled with a real patient's twin output. The watch shows today's risk as a ring. The phone app, My lungs today, says it in plain words, and shows the air for the next three days.", [("scroll", "What the patient sees")]),
  ("A", "For a high-risk patient, the watch gives one clear message. Your rescue inhaler use is up. A flare-up may be coming. Your doctor has been told.", [("click", "High risk")]),
  ("A", "And if oxygen drops below 90? Simply: call your doctor now.", [("click", "Urgent: oxygen below 90%")]),
  ("A", "There are three kits. The minimum is any smartwatch plus a fingertip oximeter. The full kit adds a smart inhaler clip, like ADHERO from Lupin and Aptar, sold in India. And for families who can't afford a watch, there's a no-watch kit: just a phone and an oximeter.", [("scroll", "Three ways to equip a patient")]),
  ("A", "To be clear: in this prototype, readings are simulated or typed in. These device connections are our integration plan, using each platform's published data interface.", [("scroll", "How a reading travels")]),
 ]),
 ("10. Evidence and honesty", ("app", BASE + "page=Model%20and%20evidence&day=2019-11-05"), [
  ("Y", "Now, the honest part. What's real, and what isn't?", [], 0.95),
  ("Y", "All the air quality and weather data is real. The training patients are synthetic. The health records come from Synthea, an open-source generator of synthetic hospital records, plus 120 younger Indian patients we added. The watch readings and flare-ups come from our own simulator, and every effect size in it comes from a published study, or is labelled as our assumption.", [("scroll", "How much of the data is real")]),
  ("Y", "Why simulate? Because we couldn't find any open dataset of COPD patients with wearable data and labelled flare-ups. That's the honest gap, and it's our next step.", []),
  ("Y", "On 126 patients the model never saw, the accuracy score, AUROC, is 0.815. Published real-world COPD tools score between 0.68 and 0.85. The twin warned of two in every three flare-ups, one to three days ahead, with less than one false alert per patient per month. But remember: the patients are simulated. So this proves the pipeline works. It's not clinical accuracy.", [("slide", 7)]),
  ("Y", "The chart also shows where the signal comes from. Wearables alone score 0.82. Air and weather alone, only 0.57. Air can't tell you which three days one person will flare up. It tells you when risk rises across a city and a season, and that's what powers the smog warnings.", []),
  ("Y", "We also tested the twin on real people: 100 de-identified hospital patients from the open MIMIC-III database, aged 18 to 90. It scored all 75 with enough data, with zero crashes. And its risk rose with real worsening signs, with a rank correlation of 0.73.", [("app",), ("scroll", "Stress test on 100 real patients")]),
  ("Y", "And the limits? It didn't predict death in intensive care, which is a different event from a flare-up at home. Real hospital patients are sicker than our synthetic ones. And the groups are small. So this is a stress test. Not clinical validation.", [("scroll", "Real-data check")]),
 ]),
 ("11. Pilot plan and close", ("slides", [12, 13, 14]), [
  ("A", "So who does this help? The doctor gets a ranked list of who to call, and why. The community health worker can follow hundreds of patients and visit the few who need it. The family gets early warning, and plain advice on smog days.", []),
  ("A", "Here's our plan, in three phases.", [("slide", 13)]),
  ("A", "First, validate. We want to partner with a pulmonology clinic and follow real COPD patients through one smog season. The test is simple: how many flare-ups does the twin catch early, and how many false alarms does it raise?", []),
  ("A", "Second, the patient app. A daily check-in that works with just a phone and an oximeter, alerts on SMS and WhatsApp, and Hindi and regional languages.", []),
  ("A", "And third, scale. Live air-quality forecasts, links to ABHA health records, and rollout through community health workers.", []),
  ("Y", "One last thing. We're two MBA students, and neither of us writes code. We built BreatheTwin with an AI assistant, and put our effort into the questions a clinic would ask. Is it safe? Is it honest about its data? Would a doctor actually use it? And it's all open source.", []),
  ("A", "BreatheTwin. Early warning, easier breathing. Thank you!", [("slide", 14)], 0.95),
  ("Y", "Thank you! The live demo and the code are linked in our submission.", []),
 ]),
]

# How the voices should say things written differently on screen
SAY = [("COPD", "C O P D"), ("PM2.5", "P M 2.5"), ("AUROC", "A U R O C"), ("MIMIC-III", "Mimic three"),
       ("LightGBM", "Light G B M"), ("CPCB", "C P C B"), ("N95", "N 95"), ("ABHA", "Abha"), ("SMS", "S M S"),
       ("MBA", "M B A"), ("SDA Bocconi", "S D A Bocconi"), ("WHO", "W H O"), ("ADHERO", "Adhero"), ("MOMENTUM", "Momentum"),
       ("0.815", "0 point 8 1 5"), ("0.82", "0 point 8 2"), ("0.57", "0 point 5 7"), ("0.68", "0 point 6 8"),
       ("0.85", "0 point 8 5"), ("0.73", "0 point 7 3"), ("0.3 percent", "0 point 3 percent"), ("GOLD", "Gold"),
       ("1,900", "1900"), ("3,100", "3100"), ("4,000", "4000"), ("bidi", "beedi"), ("Okay", "Okay")]
VOICE = {"A": ("af_heart", "en-us", 1.0), "Y": ("am_michael", "en-us", 1.04)}


def say(text):
    for a, b in SAY:
        text = text.replace(a, b)
    return text
