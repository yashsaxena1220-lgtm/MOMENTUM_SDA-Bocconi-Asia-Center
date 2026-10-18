# MIMIC-III Clinical Database Demo v1.4 (real, de-identified)

100 real ICU patients from Beth Israel Deaconess Medical Center, Boston (2001-2012), released openly by PhysioNet.
Used only for the real-data stress test (`src/stress_test_real.py`), never for training.

- Source: Johnson AEW, Pollard TJ, Mark RG. *MIMIC-III Clinical Database Demo* (v1.4). PhysioNet, 2019. https://doi.org/10.13026/C2HM2Q
- Licence: Open Database License (ODbL) v1.0. This folder is a derived extract and is shared under the same licence.
- Copy taken from the `mimic.demo` data package (https://github.com/eth-mds/mimic-demo), which mirrors the PhysioNet files.

What is here (only the columns the stress test needs):

| File | Contents |
|---|---|
| `patients.csv` | sex, shifted birth and death times |
| `admissions.csv` | admission times, in-hospital death flag |
| `icustays.csv` | ICU stay start and end |
| `diagnoses_icd.csv` | ICD-9 diagnosis codes |
| `vitals.csv.gz` | 47,362 real bedside readings (47,214 after the stress test drops physically impossible values) of heart rate, breathing rate and SpO2, timed in hours from ICU admission |

Dates in MIMIC are shifted into the future and ages above 89 are shifted to about 300 for privacy; the stress test caps age at 90.
