# CLAUDE.md — Analyst (Nexon AI Solutions)

Read this first, every session. Then read `docs/PRD.md`, `docs/ARCHITECTURE.md`, and the current milestone in `TASKS.md`.

## What this is
Analyst is a trust-first data preparation and insight platform. A user uploads a messy CSV/Excel file; the system profiles it deterministically, an LLM *proposes* cleaning steps, the user approves, approved steps are applied, a dashboard is generated, and the user exports cleaned data + a reproducible script + a quality report.

## Non-negotiable invariants (never violate, never "temporarily" bypass)
1. **No silent mutation.** Data changes only via an approved `cleaning_proposal` that becomes a `transform_step`. Raw versions are immutable.
2. **The LLM never executes anything and never writes code that we run.** It emits JSON validated against `schemas/*.json`. Anything failing validation is discarded and logged, never repaired by guessing.
3. **All numbers are computed deterministically** (Polars/DuckDB). The LLM narrates only through placeholders bound to computed values (`{{kpi_id}}`). A narrative containing a number not traceable to a placeholder is rejected.
4. **Every transform op has three emitters from one definition**: Polars executor, Python-script emitter, DuckDB-SQL emitter. Add an op = implement all three + tests + schema entry (see `.claude/commands/add-operation.md`).
5. **Uploaded data is hostile.** Validate file type by content, cap size/rows/cols, neutralize CSV formula injection on export, never `eval`/`exec`, never interpolate user strings into SQL (use the query builder with identifier allow-listing + bound params).
6. **Only column metadata + a small, PII-masked sample goes to the LLM.** Never the full dataset. Log every LLM call (`llm_calls`) without raw cell values.
7. **Reproducibility:** running the exported script on the raw file must produce a cleaned file with the same content hash as the app's cleaned export. This is a CI test.

## Stack
Backend: Python 3.12, FastAPI, SQLAlchemy 2 (async) + Alembic, Postgres 16, Redis 7, Celery, Polars, DuckDB, Pandera, Pydantic v2, MinIO/S3 (boto3), Anthropic SDK (structured output via tool-use JSON schema), structlog, pytest, ruff, mypy --strict.
Frontend: React 18 + TypeScript + Vite, TanStack Query, Zustand, vega-embed (Vega-Lite) as the primary renderer, Plotly for scatter/box where needed, Tailwind, Vitest + Playwright.
Infra: Docker Compose (dev), GitHub Actions CI, OpenTelemetry-ready logging.

## Repo layout
```
backend/app/{api,core,db,services,ops,profiling,llm,dashboard,export,workers}
backend/tests/{unit,integration,e2e}
frontend/src/{pages,components,features,lib}
benchmarks/{datasets,ground_truth,runner}
db/schema.sql              # source of truth for the data model; Alembic migrations must match
schemas/                   # JSON Schemas: transform step, LLM proposal output, chart spec
docs/                      # PRD, ARCHITECTURE, API, SECURITY, EVALUATION
```

## Commands (create Makefile targets as part of M0)
- `make dev` — docker compose up (db, redis, minio, api, worker, web)
- `make test` — backend pytest + frontend vitest
- `make lint` — ruff, mypy --strict, eslint, tsc --noEmit
- `make bench` — run the cleaning benchmark, write `benchmarks/results/latest.json`
- `make migrate` — alembic upgrade head

## Working agreements
- Work **one milestone task at a time** from `TASKS.md`. Tick the checkbox only when acceptance criteria pass and tests are green.
- Write the test first for ops, profiling rules, validators, and the query builder.
- Small commits, Conventional Commits (`feat(ops): add impute median`).
- Type everything; no `Any` without a comment justifying it. Pydantic models at every boundary.
- Prefer lazy Polars (`scan_csv`, `LazyFrame`) over eager loads. No pandas in the hot path.
- Idempotent Celery tasks; every job has a status row, progress, and a structured error.
- If a requirement is ambiguous, check `docs/PRD.md` "Open questions"; if still unclear, ask before building.
- Do not add dependencies without a one-line justification in the commit message.

## Definition of done (per task)
Acceptance criteria met · unit + integration tests added · `make lint` clean · docs/schema updated if behaviour changed · no invariant above weakened.
