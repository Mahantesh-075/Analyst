# AGENTS.md — Analyst Invariants & Architecture Constraints

This file documents the core invariants and architectural rules that all agents and developers must strictly follow when working on Analyst. Never bypass or weaken any invariant.

---

## 1. Non-Negotiable Invariants

1. **No Silent Mutation:** Data changes only through a user-approved `cleaning_proposal` that becomes a recorded `transform_step` row. Raw dataset versions are strictly immutable (enforced by PostgreSQL trigger `trg_versions_immutable` on `dataset_versions`).
2. **LLM Never Executes Anything and Never Generates Executable Code:** The LLM produces strictly schema-validated JSON (conforming to `schemas/*.json`). Invalid output is retried once with the schema error; if still invalid, it is logged and dropped. It is never guessed or auto-repaired.
3. **All Displayed Numbers Are Deterministically Computed:** Polars and DuckDB compute every metric, quantile, outlier, KPI, and preview. LLM narrative generation uses strict placeholders (e.g. `{{kpi_id}}`) bound to computed values. Any digit in a narrative template outside a placeholder causes immediate rejection.
4. **Unified Op Definition with Closed Registry:** Every transform op is implemented via the `Op` protocol in `app/ops/` with three synchronized outputs:
   - Polars executor (`apply`)
   - Python-script generator (`to_python`)
   - DuckDB SQL CTE generator (`to_sql`)
   - Computed preview function (`preview`)
   Ops are a closed registry (`app/ops/registry.py`). No raw user strings or unchecked code may ever be executed.
5. **Uploaded Data is Hostile:**
   - Content-based magic byte inspection rejects macros (`.xlsm`), executables, zip bombs, and polyglots.
   - Enforce size (200 MB), row (2M), and column (500) caps.
   - Neutralize formula injection on CSV export (prefixing `= + - @ \t \r` with `'`).
   - SQL is executed only via the safe Query Builder with identifier allow-listing against table schema, enum operators, bound parameters, DuckDB memory limits, and query timeouts.
6. **Zero PII Exposure to LLMs / Logs:**
   - PII is detected deterministically (email, phone, Aadhaar/PAN, names).
   - Only column metadata and a small PII-masked sample (20 rows) are ever sent to an LLM provider.
   - `llm_calls` audit table logs input hash, prompt version, tokens, and latency, but never raw cell data.
   - The entire platform must operate fully and reliably when `llm_enabled=false` (rule-only mode).
7. **100% Reproducibility Guarantee:**
   - Executing the exported Python script or DuckDB SQL script on the raw file must produce a cleaned dataset with the identical canonical content hash (SHA-256 over normalized Parquet rows sorted by original row index) as the system's cleaned version. This is enforced by automated CI property tests.

---

## 2. Architecture & Code Boundaries

- **Routers (`app/api/`)**: Handle HTTP serialization, parameter validation, and status codes. Must NOT contain business logic.
- **Services (`app/services/`)**: Orchestrate business logic, Celery jobs, and DB transactions. Must NEVER import FastAPI or Starlette request objects.
- **Repository Layer (`app/db/repositories/`)**: All DB queries must be scoped by `owner_id`. Any request accessing another user's dataset must return a `404 NOT_FOUND` (never a `403 FORBIDDEN` to prevent resource enumeration).
- **Pure Ops and Profiling (`app/ops/`, `app/profiling/`)**: Pure functions that operate on Polars `LazyFrame` or in-memory arrays. Must be 100% unit-testable without a database or running network services.
- **Workers (`app/workers/`)**: Celery tasks are thin wrappers that invoke services. Every task is idempotent, tracks progress in the `jobs` table, and logs structured errors. Datasets are locked using Redis to serialize jobs per dataset.
- **Frontend (`frontend/`)**: React 18, TypeScript, Vite, TanStack Query for server state, Zustand for client state, Tailwind CSS for styling, Vega-Lite/vega-embed with Plotly for interactive visualisations.
