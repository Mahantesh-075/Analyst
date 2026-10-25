# Product Requirements Document — Analyst

**Company:** MAHANT · **Status:** v1.0 draft · **Owner:** Mahant

## 1. Summary
Analyst turns a messy spreadsheet into a clean dataset, an interactive dashboard, and a reproducible cleaning script, with the user approving every change. Its edge over "AI cleans your data" tools is **transparency, reproducibility, and a focus on small organizations without a data team**.

## 2. Problem
Small businesses and NGOs keep critical data in inconsistent CSV/Excel exports (mixed date formats, "N/A" vs blank, duplicate rows, typos in categories, PII in free columns). They cannot afford an analyst, and generic AI tools (a) change data silently, (b) give non-reproducible results, (c) hallucinate insights. Wrong decisions follow.

## 3. Target users
| Persona | Needs | Technical level |
|---|---|---|
| **Priya, shop owner** | Weekly sales/inventory insights from POS exports | Excel only |
| **Arun, NGO programme officer** | Clean beneficiary/survey data, share a report with donors, protect PII | Basic |
| **Sana, volunteer analyst** | Reproducible cleaning she can audit and rerun | Python/SQL literate |

## 4. Goals
- G1: Upload to first useful dashboard in **under 5 minutes** for a typical 50k-row file.
- G2: **Zero silent changes**; 100% of mutations are user-approved and logged as lineage.
- G3: Exported script reproduces the app's cleaned output exactly.
- G4: Cleaning quality is **measured**, not claimed (benchmark with ground truth).
- G5: Every dashboard number is traceable to a deterministic computation.

## 5. Non-goals (v1)
Real-time/streaming data · multi-table joins and data modelling · write-back to source systems · fine-tuning our own LLM · mobile app · multi-tenant org/RBAC beyond single-owner datasets · rendering inside Power BI (see FR-604).

## 6. Success metrics
| Metric | Target |
|---|---|
| Benchmark cell-level cleaning F1 (applied fixes vs ground truth) | ≥ 0.90 on the v1 benchmark |
| Proposal acceptance rate (proxy for proposal quality) | ≥ 70% |
| Exported-script reproducibility test | 100% pass |
| LLM schema-validation failure rate | < 2% after one retry |
| P95 profile time, 100 MB CSV | < 60 s |
| Narrative numbers not traceable to computed values | 0 |

## 7. Functional requirements

### 7.1 Ingestion
- FR-101 Upload CSV, TSV, XLSX (multi-sheet: user picks the sheet). Max 200 MB, 2M rows, 500 columns (configurable).
- FR-102 Detect encoding, delimiter, header row, and decimal/thousands separators; show detections and let the user override.
- FR-103 Content-based file type validation; reject executables, archives, and macro-enabled files (`.xlsm`).
- FR-104 Store the raw file immutably (`dataset_versions.kind = raw`) with SHA-256.

### 7.2 Deterministic profiling
- FR-201 Per column: inferred dtype, null %, distinct count, min/max/mean/median/std/quantiles, top-k values, string length stats, mixed-type detection.
- FR-202 Dataset level: exact duplicate rows, constant columns, high-cardinality ID columns, row/col counts.
- FR-203 Outliers via IQR and robust z-score (flag, never remove).
- FR-204 Missing-token detection (`N/A`, `-`, `null`, `?`, empty strings) distinct from true nulls.
- FR-205 Date-format inference including day-first/month-first ambiguity detection.
- FR-206 PII detection (email, phone, Aadhaar-/PAN-like patterns, name heuristics) with per-column confidence; PII columns flagged and masked in LLM samples.
- FR-207 Profiling output is a versioned JSON document stored per dataset version; computed with Polars/DuckDB only (no LLM).

### 7.3 Proposals (rule engine + LLM)
- FR-301 A rule engine emits proposals for unambiguous issues (trim whitespace, missing tokens to null, exact duplicates, type casts that parse >= 99%).
- FR-302 The LLM receives column metadata + masked sample and returns, via structured output: column semantics (`semantic_type`, description, confidence) and **additional proposals** for ambiguous issues (category harmonization, date format choice, imputation strategy, column splits).
- FR-303 Each proposal contains a typed `TransformStep` (op registry only), a human-readable reason, confidence, severity, and a **computed before/after impact preview** (rows/cells affected, 5 sample diffs, distribution change).
- FR-304 User can accept, reject, or edit params of each proposal; bulk-accept for `source=rule` high-confidence items.
- FR-305 Invalid LLM output is retried once with the validation error; if still invalid it is dropped and recorded, never auto-fixed.
- FR-306 Imputation proposals disclose the strategy and share of values imputed; a column with > 30% missing defaults to a "drop column or leave" suggestion instead of imputation.

### 7.4 Apply and lineage
- FR-401 Applying accepted proposals produces a new immutable `cleaned` version; each step is a `transform_step` row (rows before/after, cells changed, engine version).
- FR-402 Steps run in `order_index` order on a Polars LazyFrame; any failure rolls back the whole apply (no partial versions).
- FR-403 Pandera validation of the cleaned output against a schema derived from accepted semantics (dtype, nullability, ranges); violations are reported, not hidden.
- FR-404 Undo = create a new version from the raw plus a modified step list (no in-place edits).

### 7.5 Dashboard
- FR-501 The LLM proposes a **chart spec** (JSON, validated against `schemas/chart_spec.schema.json`) using only existing columns; the backend executes each chart's declarative query through a safe query builder on DuckDB and returns the data.
- FR-502 Chart types v1: KPI card, bar, line, histogram, scatter, box, pie (max 8 slices), table.
- FR-503 Narrative insights are template strings with placeholders bound to computed values; the validator rejects free numbers.
- FR-504 Users can add/remove/reorder charts and change chart type; the dashboard is saved per dataset version.
- FR-505 Shareable read-only dashboard link (token, revocable) in v1.1.

### 7.6 Export
- FR-601 Cleaned dataset: CSV (formula-injection-safe) and Parquet.
- FR-602 **Reproducible script**: standalone Python (Polars) and SQL (DuckDB) files containing exactly the applied steps, with comments citing each proposal's reason. Runs with no Analyst dependency.
- FR-603 Data-quality report (HTML + PDF): before/after profile, every applied/rejected step, lineage, validation results.
- FR-604 **Power BI-ready export (v1.1):** Power BI cannot render our JSON chart spec. Provide the cleaned Parquet/CSV plus a generated **Power Query (M) script** built from the same step definitions.

### 7.7 Accounts and projects
- FR-701 Email + password auth (argon2id), JWT access + rotating refresh tokens; per-user dataset isolation enforced in every query.
- FR-702 Dataset list, rename, soft delete, hard-delete purge job (raw files + versions) within 24 h of request.
- FR-703 Retention: uploaded data auto-purged after N days (default 30) unless extended.

### 7.8 Ask-your-data (v1.1, stretch)
NL question to validated query spec (same builder as charts, never raw SQL) to result + chart. Evaluated on a question/answer set.

## 8. Non-functional requirements
- **Security:** see `docs/SECURITY.md`; OWASP ASVS L1 baseline.
- **Performance:** streaming ingestion; per-column parallel profiling; async jobs with progress; API P95 < 300 ms for non-job endpoints.
- **Reliability:** idempotent jobs, retries with backoff, dead-letter handling, resumable after worker crash.
- **Observability:** structured logs with request/job IDs; metrics for job duration, LLM latency/cost/failure rate; health endpoints.
- **Cost:** per-dataset LLM token budget with hard cap; cache LLM results by (schema + sample hash, prompt version).
- **Accessibility:** WCAG 2.1 AA; every chart has a table view.
- **Privacy:** PII masked before LLM; user can disable the LLM entirely (rule-only mode still works).

## 9. Primary user flow
Upload → confirm parse settings → (job) profile → review profile and semantics → review proposals with previews → accept/reject/edit → (job) apply → validation report → (job) generate dashboard → edit dashboard → export data, script, report.

## 10. Scope by release
- **MVP (M0–M7):** 7.1–7.4, 7.5 (FR-501–504), 7.6 (FR-601–603), 7.7 basics, benchmark v1.
- **v1.1:** share links, Power BI export, ask-your-data, SSO.
- **Later:** saved recipes for recurring files, multi-file joins, org workspaces.

## 11. Risks
| Risk | Mitigation |
|---|---|
| LLM proposes a harmful or wrong fix | Approval gate, previews, op-registry-only output, benchmark, confidence thresholds |
| LLM cost/latency | Metadata-only prompts, caching, token budgets, rule-only fallback |
| Large files exhaust memory | Lazy/streaming Polars + DuckDB, size caps, chunked profiling |
| PII leakage | Detection, masking, no raw data in prompts/logs, retention purge |
| Crowded market | Niche (SMB/NGO); reproducibility + lineage as the differentiator |
| Scope creep | Milestone gates in `TASKS.md`, non-goals list |

## 12. Open questions
1. Demo hosting target? Default: Docker Compose on a single VM / free-tier cloud.
2. Default LLM provider/model? Default: Anthropic, configurable via env; abstraction in `app/llm/client.py`.
3. Regional-language headers (Hindi/Kannada) in v1? Default: UTF-8 safe, English-only semantics.

## 13. Glossary
**Op**: a typed, registered transform. **Step**: an applied op instance. **Proposal**: a suggested step awaiting a decision. **Version**: an immutable dataset snapshot. **Lineage**: ordered steps connecting versions.
