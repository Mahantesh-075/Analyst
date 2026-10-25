# API — Analyst (v1, REST + SSE)

Base: `/api/v1`. JSON. Auth: `Authorization: Bearer <access_jwt>`. All dataset-scoped routes enforce `owner_id = current_user.id` (404, never 403, on foreign IDs).
Errors: `{ "error": { "code": "STRING_CODE", "message": "...", "details": {} }, "request_id": "..." }`.
Long work returns `202 { "job_id": "..." }`; poll `GET /jobs/{id}` or subscribe to `GET /jobs/{id}/events` (SSE).
Mutating job-starting endpoints accept `Idempotency-Key`.

## Auth
| Method | Path | Notes |
|---|---|---|
| POST | /auth/register | `{email,password,display_name}`; password >= 10 chars |
| POST | /auth/login | returns `{access_token, refresh_token}`; rate-limited |
| POST | /auth/refresh | rotates refresh token; reuse of a revoked token revokes the family |
| POST | /auth/logout | revokes refresh token |
| GET/PATCH | /me | profile, `llm_enabled` toggle |

## Datasets and versions
| Method | Path | Notes |
|---|---|---|
| POST | /datasets | `{name, filename, size_bytes}` → `{dataset_id, upload: {url, fields}}` (presigned POST with size/type conditions) |
| POST | /datasets/{id}/ingest | after upload; body `{parse_settings?}` → 202 job (`ingest`) |
| GET | /datasets | paginated (`cursor`, `limit`), filter `status` |
| GET | /datasets/{id} | metadata, status, current version |
| PATCH | /datasets/{id} | rename, description, `retention_until` |
| DELETE | /datasets/{id} | soft delete + enqueue purge |
| GET | /datasets/{id}/versions | raw + cleaned versions |
| GET | /datasets/{id}/versions/{vid}/preview | first N rows (N <= 200), paginated, typed |

## Profiling
| Method | Path | Notes |
|---|---|---|
| POST | /datasets/{id}/profile | 202 job (`profile`) |
| GET | /datasets/{id}/versions/{vid}/profile | dataset summary + column profiles |
| PATCH | /datasets/{id}/columns/{name}/semantics | user override of `semantic_type`/description |

## Proposals
| Method | Path | Notes |
|---|---|---|
| POST | /datasets/{id}/proposals/generate | 202 job (`propose`); respects `llm_enabled` (rule-only otherwise) |
| GET | /datasets/{id}/proposals | filter `status`, `source`, `column` |
| PATCH | /datasets/{id}/proposals/{pid} | `{status: accepted|rejected}` and/or `{edited_params}` (re-validated + preview recomputed) |
| POST | /datasets/{id}/proposals/bulk | `{ids[], status}` or `{rule: "high_confidence_rules"}` |
| POST | /datasets/{id}/apply | applies all `accepted` proposals → 202 job (`apply`) → new cleaned version |
| GET | /datasets/{id}/versions/{vid}/lineage | ordered `transform_steps` |
| GET | /datasets/{id}/versions/{vid}/validation | Pandera result |

## Dashboard
| Method | Path | Notes |
|---|---|---|
| POST | /datasets/{id}/versions/{vid}/dashboard/generate | 202 job (`dashboard`) |
| GET | /datasets/{id}/versions/{vid}/dashboard | spec + computed data + rendered narrative |
| PUT | /datasets/{id}/versions/{vid}/dashboard | user-edited spec; re-validated; queries re-run |
| POST | /datasets/{id}/versions/{vid}/dashboard/query | ad-hoc validated query object (same builder) |

## Exports
| Method | Path | Notes |
|---|---|---|
| POST | /datasets/{id}/versions/{vid}/exports | `{kind}` → 202 job (`export`) |
| GET | /datasets/{id}/exports | list |
| GET | /exports/{eid}/download | 302 to a short-lived presigned URL |

## Jobs and ops
| Method | Path | Notes |
|---|---|---|
| GET | /jobs/{id} | `{status, progress, result, error}` |
| GET | /jobs/{id}/events | SSE: `progress`, `done`, `error` |
| POST | /jobs/{id}/cancel | best-effort |
| GET | /ops | registry listing (name, params schema) for the UI |
| GET | /healthz, /readyz | liveness / readiness (db, redis, object store) |

## Error codes (stable)
`AUTH_INVALID`, `RATE_LIMITED`, `FILE_TYPE_REJECTED`, `DATASET_TOO_LARGE`, `PARSE_FAILED`, `PROPOSAL_INVALID_PARAMS`, `APPLY_FAILED`, `VALIDATION_FAILED`, `LLM_UNAVAILABLE`, `LLM_BUDGET_EXCEEDED`, `SPEC_INVALID`, `NOT_FOUND`, `CONFLICT`.
