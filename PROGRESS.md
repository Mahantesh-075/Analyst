# Progress — Analyst Build

## Current Status (2026-10-25)

- **Overall State:** Step 0 complete. Ready to begin Milestone 0 (Foundation).
- **Environment:**
  - Python 3.12 (via `uv` 0.13.5 at `C:\Users\mahan\anaconda3\Scripts\uv.exe`)
  - Node.js 24.19.0 & npm 12.2.0
  - Git initialized in `c:\Users\mahan\.gemini\analyst`
  - Linux/WSL2 host: Ubuntu 26.04 available with Docker
- **Source of Truth Documents:**
  - `AGENTS.md` (Created, defines non-negotiable invariants)
  - `CLAUDE.md` (Verified)
  - `docs/PRD.md` (Verified)
  - `docs/ARCHITECTURE.md` (Verified)
  - `docs/API.md` (Verified)
  - `docs/SECURITY.md` (Verified)
  - `docs/EVALUATION.md` (Verified)
  - `db/schema.sql` (Verified)
  - `schemas/*.json` (`chart_spec`, `llm_proposal_output`, `transform_step` verified)

## Milestone Tracker

| Milestone | Status | Verified Tasks | Notes / Blockers |
|---|---|---|---|
| **M0: Foundation** | COMPLETED | 4 / 4 | Baseline schema, Alembic stamped, Postgres/Redis/MinIO verified, healthchecks active, 9 backend tests + 1 frontend test passing, 0 lint/mypy errors |
| **M1: Auth & Dataset Shell** | IN PROGRESS | 0 / 3 | Starting T1.1 Auth Services |
| **M2: Ingestion** | PENDING | 0 / 4 | Blocked on M1 |
| **M3: Profiling** | PENDING | 0 / 6 | Blocked on M2 |
| **M4: Op Registry & Apply Engine** | PENDING | 0 / 5 | Blocked on M3 |
| **M5: Proposals (Rules + LLM)** | PENDING | 0 / 6 | Blocked on M4 |
| **M6: Dashboard** | PENDING | 0 / 5 | Blocked on M5 |
| **M7: Export & Report** | PENDING | 0 / 3 | Blocked on M6 |
| **M8: Benchmark & Launch** | PENDING | 0 / 6 | Blocked on M7 |

## Detected Broken Items
- None. Clean greenfield start.

## Execution Plan to Reach Done
1. **M0 Foundation**: Backend `pyproject.toml` with dependencies, `frontend` Vite React TS template, lint/typecheck/test passing on empty scaffolds, Docker Compose service verification, settings/logging/errors, Alembic migration matching `db/schema.sql`, owner-scoped repository.
2. **M1 Auth & Dataset Shell**: Argon2id auth, JWT + rotating refresh, dataset CRUD with presigned uploads, soft delete, cross-user 404 isolation tests, frontend auth/dataset list/upload view.
3. **M2 Ingestion**: File sniffing, magic byte checks, size/row/column caps, parse detection & override, canonical Parquet conversion, SSE job progress.
4. **M3 Deterministic Profiling**: Column stats, missing tokens, date format inference, outliers (IQR/robust z), PII detection & masking, persistence, profile UI.
5. **M4 Op Registry & Apply Engine**: 14 ops with Polars/Python/DuckDB emitters, Hypothesis property tests (executor == Python == SQL), LazyFrame atomic apply, Pandera schema validation, script exporters, CI reproducibility test.
6. **M5 Proposals**: Rule engine, LLM client abstraction + token budgeting + caching, structured output validation (retry once, drop on failure), proposal review UI, prompt injection tests, rule-only fallback mode.
7. **M6 Dashboard**: Chart spec models, parameterized query builder with fuzz tests, KPI calculations, narrative validator (zero untraceable digits), `<ChartRenderer>` (Vega-Lite + Plotly), accessibility.
8. **M7 Export & Report**: Formula-safe CSV, Parquet, Jinja2/WeasyPrint quality report (HTML/PDF), presigned download API.
9. **M8 Hardening & Launch**: 4 benchmark datasets with seeded defects, `make bench` meeting all targets (F1 >= 0.90, damage rate 0 for rules, 100% reproducibility), security hardening (CORS, headers, rate limits, audit), backup/restore scripts, demo account & dataset, documentation sync.
