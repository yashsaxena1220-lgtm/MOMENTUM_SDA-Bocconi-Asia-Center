# Regenerating the Synthea COPD cohort

Synthea (https://github.com/synthetichealth/synthea), `synthea-with-dependencies.jar` from the
`master-branch-latest` release, Java 17+. Two batches of 150 living COPD patients each, with the EHR
history ending on 1 March 2019 (`-r 20190301`), the first day of our monitoring year.

```bash
for SEED in 2026 2027; do
java -Xmx5g -jar synthea-with-dependencies.jar -p 150 -s $SEED -cs $SEED -a 45-85 -r 20190301 -k keep_copd.json \
  --exporter.csv.export=true --exporter.fhir.export=false --exporter.hospital.fhir.export=false \
  --exporter.practitioner.fhir.export=false \
  --exporter.csv.excluded_files=claims.csv,claims_transactions.csv,patient_expenses.csv,imaging_studies.csv,payer_transitions.csv \
  --exporter.baseDirectory=./out_$SEED Massachusetts
done
```

`keep_copd.json` keeps only patients with an active diagnosis of pulmonary emphysema (SNOMED 87433001) or
chronic obstructive bronchitis (SNOMED 185086009), the two codes Synthea's COPD module assigns.

Each batch took about 20 minutes on 2 CPU cores. Run 1 produced 399 records (150 alive, 249 died before
March 2019); run 2 produced 420 (150 alive). Only the 300 living patients are used.

The repo stores a trimmed copy in `data/raw/synthea_csv/`: those 300 patients, and only the observation codes
the pipeline reads (the full output is about 200 MB, over GitHub's file limit). Direct identifiers that Synthea
fabricates (SSN, licence, passport, address, coordinates) are dropped.
