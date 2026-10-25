# TASKS — Analyst build plan for Claude Code

Work top to bottom. One task at a time. Tick a box only when its acceptance criteria (AC) pass and `make lint test` is green. Each milestone ends with a demoable state.

## M0 — Foundation
- [ ] T0.1 Monorepo scaffold: `backend/` (uv + pyproject, ruff, mypy strict, pytest), `frontend/` (Vite React TS, eslint, vitest), `Makefile`, pre-commit, GitHub Actions CI (lint, test, schema-drift check). AC: `make lint test` passes on empty projects in CI.
- [ ] T0.2 `infra/docker-compose.yml` up: postgres, redis, minio, api, worker, web; healthchecks. AC: `make dev` brings all healthy; `/healthz` and `/readyz` return 200.
- [ ] T0.3 Settings (pydantic-settings), structlog JSON logging with request IDs, typed error envelope + handlers. AC: unit tests for error shape.
- [ ] T0.4 Alembic baseline from `db/schema.sql`; repository base class enforcing `owner_id` scoping. AC: `make migrate` creates schema; test that unscoped queries are impossible via the base class.

## M1 — Auth and dataset shell
- [ ] T1.1 Register/login/refresh/logout (argon2id, JWT, rotating refresh with reuse detection, rate limit). AC: security tests 1–4 subset for auth pass.
- [ ] T1.2 Dataset CRUD, presigned upload with size/type conditions, soft delete + purge job stub. AC: cross-user access returns 404 on every route (parametrized test).
- [ ] T1.3 Frontend: login, dataset list, upload with progress. AC: Playwright upload happy path.

## M2 — Ingestion
- [ ] T2.1 Content sniffing + allow-list + caps (`FILE_TYPE_REJECTED`, `DATASET_TOO_LARGE`). AC: rejection fixtures from `docs/SECURITY.md` test 1.
- [ ] T2.2 Parse-settings detection (encoding, delimiter, header row, decimal/thousands, XLSX sheet list) + user override endpoint. AC: fixture matrix of 20 odd CSVs parsed correctly.
- [ ] T2.3 Convert to canonical Parquet (typed, lazy), create raw version with SHA-256, job + progress + SSE. AC: 100 MB CSV ingests within memory budget (< 1.5 GB RSS).
- [ ] T2.4 Frontend: parse-settings confirmation screen + preview table.

## M3 — Deterministic profiling
- [ ] T3.1 Column stats (dtype inference, nulls, distinct, quantiles, top-k, lengths, mixed types). AC: tests vs hand-computed fixtures.
- [ ] T3.2 Missing-token detection, duplicate rows, constant/ID columns.
- [ ] T3.3 Date-format inference with day/month ambiguity flag.
- [ ] T3.4 Outlier detection (IQR + robust z) flagging only.
- [ ] T3.5 PII detection + masking utility (email, phone, Aadhaar/PAN-like, name heuristic). AC: precision/recall report on synthetic PII set; masking is irreversible for `hash`.
- [ ] T3.6 Persist `profiles`/`column_profiles`; profile API; frontend profile page. AC: P95 < 60 s on 100 MB.

## M4 — Op registry and apply engine (the core)
- [ ] T4.1 Op protocol + registry + schema generator (`make schemas`), drift check in CI. AC: generated `schemas/transform_step.schema.json` matches committed file.
- [ ] T4.2 Implement ops in this order, each with executor + `to_python` + `to_sql` + `preview` + tests: `trim_whitespace`, `standardize_missing`, `cast_type`, `parse_date`, `drop_duplicates`, `normalize_case`, `rename_column`, `drop_column`, `drop_null_rows`, `impute`, `handle_outliers`, `map_values`, `split_column`, `mask_pii`. AC per op: Hypothesis property test asserts executor == Python script == SQL results.
- [ ] T4.3 Apply service: ordered execution on LazyFrame, atomic new cleaned version, `transform_steps` rows, rollback on failure. AC: failure injection leaves no partial version.
- [ ] T4.4 Pandera schema derivation + `validation_results`. AC: violations surfaced, never swallowed.
- [ ] T4.5 Script exporter (Python + SQL) and **reproducibility CI test** (invariant 7).

## M5 — Proposals (rules + LLM)
- [ ] T5.1 Rule engine generating proposals from the profile with impact previews. AC: precision on benchmark `source=rule` damage rate = 0.
- [ ] T5.2 LLM client abstraction, budgets, cache, `llm_calls` logging, masked-sample input builder. AC: no raw PII in recorded prompts (test over fixtures).
- [ ] T5.3 `semantics.v1` and `proposals.v1` prompts, structured output, Pydantic/JSON-schema validation, one retry, drop-on-fail. AC: invalid-output fixtures never reach the DB.
- [ ] T5.4 Proposal review API (accept/reject/edit/bulk), param re-validation, preview recompute, audit log.
- [ ] T5.5 Frontend Review page: proposal cards, before/after diff, bulk accept for high-confidence rules, edit params. AC: Playwright upload → review → apply.
- [ ] T5.6 Prompt-injection test (security test 5) and rule-only mode when `llm_enabled=false`.

## M6 — Dashboard
- [ ] T6.1 Chart spec Pydantic models mirroring `schemas/chart_spec.schema.json`; validator.
- [ ] T6.2 Query builder (allow-listed identifiers, enums, bound params, limits) + fuzz test (security test 3).
- [ ] T6.3 KPI computation, narrative placeholder binding + validator (security test 6).
- [ ] T6.4 `chart_spec.v1` + `narrative.v1` prompts; dashboard job; storage.
- [ ] T6.5 Frontend `<ChartRenderer>` (Vega-Lite + Plotly), grid layout, edit/reorder/change type, table toggle. AC: axe accessibility check passes.

## M7 — Export and report
- [ ] T7.1 CSV (formula-injection-safe, security test 2) and Parquet export.
- [ ] T7.2 Data-quality report (Jinja2 → HTML, WeasyPrint → PDF) with before/after profile, lineage, validation.
- [ ] T7.3 Exports API + presigned downloads + frontend Exports page.

## M8 — Benchmark, hardening, launch
- [ ] T8.1 Corruption generator + 4 benchmark datasets + `make bench` + metrics per `docs/EVALUATION.md`; CI regression gate.
- [ ] T8.2 Security checklist (`docs/security-checklist.md`), headers/CORS/rate limits, pip-audit + gitleaks in CI.
- [ ] T8.3 Retention purge job, hard delete, audit review.
- [ ] T8.4 Observability: metrics (job duration, LLM latency/cost/failure), dashboards, structured error tracking.
- [ ] T8.5 README with architecture diagram, benchmark table, demo GIF, live demo link; deployment guide (single VM, Compose, TLS via Caddy).
- [ ] T8.6 Demo dataset + seeded demo account for interviews.

## v1.1 backlog
Share links · Power BI export (Parquet + generated Power Query M script) · Ask-your-data (NL → validated query spec) · saved cleaning recipes for recurring files · SSO.
