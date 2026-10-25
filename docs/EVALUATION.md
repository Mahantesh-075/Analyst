# Evaluation — Analyst

Cleaning quality is measured, not claimed. `make bench` runs the whole suite and writes `benchmarks/results/latest.json`; CI fails if a tracked metric regresses by more than the tolerance.

## 1. Benchmark datasets (`benchmarks/datasets/`)
Build each by taking a **clean ground-truth table** (`ground_truth/*.parquet`) and applying a **seeded corruption generator** that logs every injected defect to `*.defects.json` (cell coordinates, defect type, original value).

| Domain | Rows | Injected defects |
|---|---|---|
| Retail sales (orders, SKU, qty, price, date, region) | 50k | mixed date formats, `N/A`/`-`/blank missing, duplicate orders, price outliers, region typos, trailing whitespace, currency symbols in numbers |
| NGO survey (age, district, income band, consent, free text) | 10k | PII in free text, inconsistent category labels (`M/Male/male`), impossible ages, numeric-as-text, missing tokens |
| Inventory (item, stock, reorder level, supplier) | 20k | negative stock, duplicated items with different casing, unit mix (kg/KG/kgs), swapped columns |
| Public civic data (complaints, ward, timestamp, status) | 30k | timezone/format mix, status synonyms, split-able address field |
Also keep 5 **real-world-style** public datasets (no ground truth) for qualitative review and speed testing.

## 2. Metrics
- **Detection recall/precision:** proposed defect cells vs `defects.json`.
- **Cell-level repair F1:** after applying all proposals auto-accepted (oracle policy: accept if it matches ground truth direction), fraction of corrupted cells restored to the ground-truth value (exact match, numeric tolerance 1e-9), penalizing damage to clean cells.
- **Damage rate:** clean cells changed by an accepted step. Target 0 for `source=rule`, < 0.1% for `llm`.
- **Proposal acceptance proxy:** share of proposals whose impact matches ground truth.
- **Reproducibility:** executor vs Python script vs SQL script content hash equality (must be 100%).
- **LLM reliability:** schema-valid rate, retry rate, token cost per 10k rows.
- **Performance:** profile and apply wall time, peak RSS on 100 MB / 1M rows.
- **Narrative integrity:** untraceable numbers = 0 (property test with adversarial templates).

## 3. Reporting
`benchmarks/results/latest.json` + a rendered table committed to the README (`make bench-report`). Track results per prompt version so prompt changes are A/B comparable. Run LLM-dependent benchmarks with recorded responses (VCR-style cassettes) in CI and live monthly.

## 4. Test pyramid
Unit (ops, profiling rules, validators, query builder) → property-based (Hypothesis: executor == emitters) → integration (API + Postgres + Redis + MinIO via testcontainers, LLM stubbed) → e2e (Playwright: upload → review → apply → dashboard → export) → benchmark (above).
