"""
Real-data check on the open MIMIC-IV Clinical Database Demo v2.2 (100 de-identified patients, ODbL 1.0).

The demo is too small to train on, so we use it to (1) run our health-record mapping on real hospital
records and (2) compare our synthetic cohort with real COPD patients. Only aggregate numbers are saved.

Input : data/raw/mimic-iv-clinical-database-demo-2.2.zip (or any mimic*demo*.zip)
Output: outputs/mimic_demo_check.csv
"""
import glob
import zipfile
import pandas as pd

from config import RAW, PROCESSED, OUTPUTS, COPD_ICD_PREFIXES

ICD = {
    "hypertension": ("401", "I10"), "diabetes": ("250", "E11"), "ischemic_heart_disease": ("414", "I25"),
    "heart_failure": ("428", "I50"), "anemia": ("285", "D64"),
}
EXACERBATION_CODES = ("49121", "J440", "J441")
VITALS = {220045: "heart_rate", 220210: "resp_rate", 220277: "spo2"}


def _open(z, table):
    name = next(n for n in z.namelist() if n.endswith(f"/{table}.csv.gz"))
    return pd.read_csv(z.open(name), compression="gzip", low_memory=False)


def main():
    found = sorted(glob.glob(str(RAW / "mimic*demo*.zip")))
    if not found:
        print("MIMIC-IV demo zip not found in data/raw/ (it is not redistributed with this repo). "
              "Skipping the real-data check; keeping the existing outputs/mimic_demo_check.csv.")
        return
    path = found[0]
    z = zipfile.ZipFile(path)
    pats, adm, dx = _open(z, "patients"), _open(z, "admissions"), _open(z, "diagnoses_icd")
    dx["icd_code"] = dx.icd_code.astype(str).str.strip()
    copd_ids = dx[dx.icd_code.str.startswith(COPD_ICD_PREFIXES)].subject_id.unique()
    p = pats[pats.subject_id.isin(copd_ids)].set_index("subject_id")
    d = dx[dx.subject_id.isin(copd_ids)]
    out = pd.DataFrame(index=p.index)
    out["age"] = p.anchor_age
    out["male"] = (p.gender == "M").astype(int)
    out["admissions"] = adm[adm.subject_id.isin(copd_ids)].groupby("subject_id").size()
    out["exacerbation_admissions"] = d[d.icd_code.isin(EXACERBATION_CODES)].groupby("subject_id").hadm_id.nunique()
    for k, codes in ICD.items():
        out[k] = out.index.isin(d[d.icd_code.str.startswith(codes)].subject_id).astype(int)

    labs, dl = _open(z, "labevents"), _open(z, "d_labitems")
    eos_items = dl[dl.label.str.contains("Eosinophil", case=False, na=False)].itemid
    eos = labs[labs.subject_id.isin(copd_ids) & labs.itemid.isin(eos_items)]
    out["eosinophils_lab_rows"] = eos.groupby("subject_id").size()
    try:
        ce = _open(z, "chartevents")
        ce = ce[ce.subject_id.isin(copd_ids) & ce.itemid.isin(VITALS)]
        out = out.join(ce.assign(v=ce.itemid.map(VITALS)).pivot_table(index="subject_id", columns="v", values="valuenum", aggfunc="median"))
    except StopIteration:
        pass
    out = out.fillna({"admissions": 0, "exacerbation_admissions": 0})

    syn = pd.read_csv(PROCESSED / "patients.csv")
    rows = [
        ("COPD patients", len(out), len(syn)),
        ("Mean age", round(out.age.mean(), 1), round(syn.age.mean(), 1)),
        ("Male %", round(out.male.mean() * 100, 1), round((syn.sex == "M").mean() * 100, 1)),
        *[(f"{k.replace('_', ' ').capitalize()} %", round(out[k].mean() * 100, 1),
           round(syn[k].mean() * 100, 1) if k in syn else None) for k in ICD],
        ("Patients with a COPD exacerbation admission %", round((out.exacerbation_admissions > 0).mean() * 100, 1), None),
        ("Median ICU heart rate", round(out.get("heart_rate", pd.Series(dtype=float)).median(), 1), round(syn.heart_rate.median(), 1)),
        ("Median ICU breathing rate", round(out.get("resp_rate", pd.Series(dtype=float)).median(), 1), round(syn.resp_rate.median(), 1)),
        ("Median ICU SpO2", round(out.get("spo2", pd.Series(dtype=float)).median(), 1), None),
    ]
    res = pd.DataFrame(rows, columns=["measure", "MIMIC-IV demo (real, Boston ICU/hospital)", "Our synthetic cohort (Synthea + India overlay)"])
    OUTPUTS.mkdir(exist_ok=True)
    res.to_csv(OUTPUTS / "mimic_demo_check.csv", index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
