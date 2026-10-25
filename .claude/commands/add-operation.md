Add a new transform op named $ARGUMENTS.

Checklist (all required):
1. `backend/app/ops/<name>.py` with Pydantic `Params`, `validate_against`, `apply` (Polars lazy), `to_python`, `to_sql`, `preview`.
2. Register in `backend/app/ops/registry.py`; run `make schemas` and commit the regenerated `schemas/transform_step.schema.json`.
3. Unit tests: normal, empty frame, all-null column, unicode, wrong dtype (expects a typed `Issue`, not an exception).
4. Hypothesis property test: executor output == executed Python script == DuckDB SQL output.
5. Add a rule or LLM-prompt example only if the op should be proposed automatically.
6. Document the op in docs/ARCHITECTURE.md op list.
Never add an op that accepts raw code, raw SQL, or regex without a length cap and a timeout-safe engine.
