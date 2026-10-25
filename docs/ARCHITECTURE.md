# Architecture — Analyst

## 1. System context
```
 React SPA ──HTTPS──> FastAPI ──> Postgres (metadata, lineage)
     ▲  ▲                │  └───> Redis ──> Celery workers ──> MinIO/S3 (raw, parquet, exports)
     │  └── SSE/WS ──────┘                      │
     │                                          ├─> Polars / DuckDB (profile, apply, query)
     └── presigned URLs (uploads/exports)       └─> LLM provider (metadata + masked sample only)
```

## 2. Pipeline (state machine on `datasets.status`)
`uploaded → profiling → profiled → proposing → review → applying → cleaned` (any → `failed`, retryable).
Each arrow is a Celery job with a row in `jobs`; the API only enqueues and reads.

1. **Ingest:** presigned upload to MinIO → content sniffing → parse settings detection → convert to Parquet (canonical working format) → `dataset_versions(kind=raw)`.
2. **Profile (deterministic):** column + dataset statistics, missing-token detection, date-format inference, outliers, PII detection → `profiles` / `column_profiles`.
3. **Propose:** rule engine proposals → LLM semantics + extra proposals (structured output, schema-validated) → every proposal is dry-run on a sample/lazy plan to compute `impact_preview` → `cleaning_proposals`.
4. **Review:** user accepts/rejects/edits. Pure DB writes, audited.
5. **Apply:** accepted proposals → ordered `TransformStep` list → executed on a Polars LazyFrame in one transaction boundary → new `cleaned` version in Parquet + `transform_steps` rows + Pandera validation.
6. **Dashboard:** LLM proposes chart spec → validated → each query run via query builder on DuckDB over the cleaned Parquet → KPI values computed → LLM narrative with placeholders → validated → stored.
7. **Export:** CSV/Parquet, Python script, SQL script, HTML/PDF report.

## 3. Op registry (the core abstraction)
One definition per op, three behaviours:

```python
class Op(Protocol):
    name: ClassVar[str]
    Params: ClassVar[type[BaseModel]]                     # Pydantic; mirrored in schemas/transform_step.schema.json
    def validate_against(self, profile: ColumnProfileSet, p: BaseModel) -> list[Issue]: ...
    def apply(self, lf: pl.LazyFrame, p: BaseModel) -> pl.LazyFrame: ...          # executor
    def to_python(self, p: BaseModel) -> str: ...                                  # Polars script line(s)
    def to_sql(self, p: BaseModel, relation: str) -> str: ...                      # DuckDB SQL CTE
    def preview(self, lf: pl.LazyFrame, p: BaseModel, n: int = 5) -> ImpactPreview: ...
```
Registry is a dict `name -> Op` populated at import; the LLM-facing JSON Schema is **generated from the registry** (`make schemas` regenerates `schemas/transform_step.schema.json`; CI fails on drift).

v1 ops: `rename_column`, `cast_type`, `trim_whitespace`, `normalize_case`, `standardize_missing`, `impute`, `drop_null_rows`, `drop_duplicates`, `parse_date`, `handle_outliers`, `map_values`, `split_column`, `drop_column`, `mask_pii`.

**Reproducibility contract:** `to_python` output concatenated into the generated script must yield a cleaned dataset whose canonical content hash equals the app's. Canonical hash = SHA-256 over the Parquet-normalized rows sorted by the original row index. Property-based tests (Hypothesis) generate random frames and assert executor == script == SQL results.

## 4. LLM layer (`app/llm`)
- `client.py`: provider abstraction (Anthropic default), timeouts, retries with jitter, token budget enforcement, cost logging.
- `prompts/`: versioned prompt files (`semantics.v1.md`, `proposals.v1.md`, `chart_spec.v1.md`, `narrative.v1.md`); version stored in `llm_calls.prompt_version`.
- Input builder: column name, dtype, null %, distinct count, top-k, **PII-masked** 20-row sample per column; PII columns send only type + statistics.
- Output: forced tool-use JSON; parsed with Pydantic; failing output retried once with the validation error, then dropped.
- Cache: `(input_hash, prompt_version)` lookup before calling.
- **Prompt-injection stance:** cell values are untrusted. They go only in clearly delimited data blocks, the system prompt states they are data, and output is structurally constrained, so an injected instruction cannot cause execution, only a (rejectable) bad proposal.

## 5. Query builder (`app/dashboard/query.py`)
Chart `query` objects `{dimensions, measures, filters, order_by, limit}` compile to parameterized DuckDB SQL:
- identifiers must exist in the version's column list (allow-list) and are quoted with `"` doubling;
- `agg` from a fixed enum; `op` from a fixed enum; values bound as parameters;
- `limit` capped at 1000; query timeout and memory limit set on the DuckDB connection (`SET memory_limit`, `statement timeout` via interrupt).
No raw SQL strings from the LLM or the client ever reach DuckDB.

## 6. Narrative binding
LLM output: `"Revenue peaked in {{peak_month}} at {{peak_revenue}}."` with `refs`. Server computes each ref from the data, formats it, and substitutes. Validator regex rejects any digit sequence in template text that is not inside a placeholder. Unbound placeholders reject the narrative.

## 7. Backend module map
```
app/api/        routers (auth, datasets, versions, proposals, dashboards, exports, jobs), deps, error handlers
app/core/       settings (pydantic-settings), security (argon2, JWT), logging, errors
app/db/         models, session, repositories (all queries scoped by owner_id)
app/services/   orchestration (DatasetService, ProposalService, ApplyService, DashboardService, ExportService)
app/ops/        registry + one module per op
app/profiling/  column stats, missing tokens, date inference, outliers, pii
app/llm/        client, prompts, input builder, validators
app/dashboard/  chart spec models, query builder, kpi, narrative
app/export/     csv (formula-safe), parquet, py/sql emitters, report (Jinja2 + WeasyPrint)
app/workers/    celery app, tasks (thin; call services), job progress helper
```
Rules: routers contain no business logic; services never import FastAPI; ops/profiling are pure and unit-testable without DB.

## 8. Frontend module map
Pages: Login, Datasets, Upload+ParseSettings, Profile, Review (proposal list + preview diff), Dashboard (grid, editable), Exports.
State: TanStack Query for server state, Zustand for UI state. Job progress via SSE (`/jobs/{id}/events`) with polling fallback. Charts rendered from the spec by one `<ChartRenderer>` component (Vega-Lite compile for bar/line/hist/pie, Plotly for scatter/box), every chart has a table toggle.

## 9. Scalability notes
- Canonical working format is Parquet; ingestion converts once, all later reads are columnar and lazy.
- Profiling parallelism per column; DuckDB for group-by-heavy stats.
- Workers scale horizontally; one dataset's jobs are serialized via a Redis lock keyed by dataset id.
- Large-file ceilings are config; above them the API returns a typed `413 DATASET_TOO_LARGE` error.
- Future: partition by tenant for object storage; move to Postgres read replicas only if metadata reads become a bottleneck (unlikely before 10^5 datasets).

## 10. Key decisions (ADR summary)
| Decision | Why | Rejected alternative |
|---|---|---|
| Op registry with three emitters | Reproducibility is the product's differentiator; one source of truth prevents drift | LLM-generated pandas code (unsafe, unreproducible) |
| Polars + DuckDB | Lazy, fast, low memory; SQL emitter parity | pandas (memory, slower) |
| JSON chart spec + query builder | No code execution; validates; renderer-agnostic | LLM-written plotting code |
| Parquet as canonical format | Typed, columnar, compressed, fast scans | CSV round-trips (type loss) |
| Celery + Redis | Mature, retries, rate limits; matches stack choice | In-process background tasks (not durable) |
| Approval gate on every change | Trust is the value proposition | Auto-clean with undo |
