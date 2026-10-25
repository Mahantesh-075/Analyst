-- Analyst data model (PostgreSQL 16). Source of truth; Alembic migrations must match.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

CREATE TYPE dataset_status   AS ENUM ('uploaded','profiling','profiled','proposing','review','applying','cleaned','failed');
CREATE TYPE version_kind     AS ENUM ('raw','cleaned');
CREATE TYPE proposal_source  AS ENUM ('rule','llm','user');
CREATE TYPE proposal_status  AS ENUM ('pending','accepted','rejected','applied','failed');
CREATE TYPE severity_level   AS ENUM ('info','low','medium','high');
CREATE TYPE job_type         AS ENUM ('ingest','profile','propose','apply','dashboard','export','purge');
CREATE TYPE job_status       AS ENUM ('queued','running','succeeded','failed','cancelled');
CREATE TYPE export_kind      AS ENUM ('csv','parquet','script_py','script_sql','report_html','report_pdf','powerbi_m');

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext NOT NULL UNIQUE,
  password_hash text   NOT NULL,                 -- argon2id
  display_name  text,
  llm_enabled   boolean NOT NULL DEFAULT true,   -- rule-only mode when false
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE refresh_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  text NOT NULL UNIQUE,
  expires_at  timestamptz NOT NULL,
  revoked_at  timestamptz,
  replaced_by uuid REFERENCES refresh_tokens(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_refresh_tokens_user ON refresh_tokens(user_id);

CREATE TABLE datasets (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name               text NOT NULL,
  description        text,
  source_filename    text NOT NULL,
  status             dataset_status NOT NULL DEFAULT 'uploaded',
  parse_settings     jsonb NOT NULL DEFAULT '{}',  -- encoding, delimiter, header_row, sheet, decimal, thousands
  current_version_id uuid,                          -- FK added below
  retention_until    timestamptz,
  deleted_at         timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_datasets_owner ON datasets(owner_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_datasets_retention ON datasets(retention_until) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_datasets_updated BEFORE UPDATE ON datasets FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE dataset_versions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id        uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  version_no        integer NOT NULL,
  kind              version_kind NOT NULL,
  parent_version_id uuid REFERENCES dataset_versions(id),
  storage_key       text NOT NULL,                 -- object-store key (raw file or parquet)
  format            text NOT NULL CHECK (format IN ('csv','tsv','xlsx','parquet')),
  size_bytes        bigint NOT NULL CHECK (size_bytes >= 0),
  sha256            char(64) NOT NULL,
  row_count         bigint,
  col_count         integer,
  created_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, version_no),
  CHECK ((kind = 'raw' AND parent_version_id IS NULL) OR kind = 'cleaned')
);
CREATE INDEX ix_versions_dataset ON dataset_versions(dataset_id);
ALTER TABLE datasets ADD CONSTRAINT fk_datasets_current_version
  FOREIGN KEY (current_version_id) REFERENCES dataset_versions(id) DEFERRABLE INITIALLY DEFERRED;

-- Raw versions are immutable.
CREATE OR REPLACE FUNCTION forbid_version_update() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'dataset_versions rows are immutable'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_versions_immutable BEFORE UPDATE ON dataset_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_version_update();

CREATE TABLE profiles (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id     uuid NOT NULL UNIQUE REFERENCES dataset_versions(id) ON DELETE CASCADE,
  engine_version text NOT NULL,
  summary        jsonb NOT NULL,                   -- dataset-level: duplicates, constant cols, issues
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE column_profiles (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id          uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  position            integer NOT NULL,
  name                text NOT NULL,
  inferred_dtype      text NOT NULL,
  semantic_type       text,                         -- filled from LLM/user, e.g. 'currency','date','id','category'
  semantic_desc       text,
  semantic_confidence real CHECK (semantic_confidence BETWEEN 0 AND 1),
  null_count          bigint NOT NULL DEFAULT 0,
  null_pct            real   NOT NULL DEFAULT 0,
  distinct_count      bigint,
  stats               jsonb NOT NULL DEFAULT '{}',  -- min/max/mean/median/std/quantiles/top_k/length stats/outliers
  missing_tokens      text[] NOT NULL DEFAULT '{}',
  pii_types           text[] NOT NULL DEFAULT '{}',
  is_pii              boolean NOT NULL DEFAULT false,
  UNIQUE (profile_id, position),
  UNIQUE (profile_id, name)
);

CREATE TABLE cleaning_proposals (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id      uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  base_version_id uuid NOT NULL REFERENCES dataset_versions(id),
  order_index     integer NOT NULL,
  op              text   NOT NULL,                  -- must exist in op registry
  params          jsonb  NOT NULL,                  -- validated against schemas/transform_step.schema.json
  target_columns  text[] NOT NULL DEFAULT '{}',
  reason          text   NOT NULL,
  impact_preview  jsonb  NOT NULL DEFAULT '{}',     -- rows/cells affected, sample diffs, distribution delta
  severity        severity_level NOT NULL DEFAULT 'info',
  source          proposal_source NOT NULL,
  confidence      real CHECK (confidence BETWEEN 0 AND 1),
  status          proposal_status NOT NULL DEFAULT 'pending',
  edited_params   jsonb,                            -- user override; original kept in params
  decided_at      timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (base_version_id, order_index)
);
CREATE INDEX ix_proposals_dataset_status ON cleaning_proposals(dataset_id, status);

CREATE TABLE transform_steps (   -- lineage: what was actually executed
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id       uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  from_version_id  uuid NOT NULL REFERENCES dataset_versions(id),
  to_version_id    uuid NOT NULL REFERENCES dataset_versions(id),
  proposal_id      uuid REFERENCES cleaning_proposals(id) ON DELETE SET NULL,
  step_no          integer NOT NULL,
  op               text  NOT NULL,
  params           jsonb NOT NULL,                  -- final params actually executed
  rows_before      bigint NOT NULL,
  rows_after       bigint NOT NULL,
  cells_changed    bigint NOT NULL,
  engine_version   text NOT NULL,
  executed_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (to_version_id, step_no)
);
CREATE INDEX ix_steps_dataset ON transform_steps(dataset_id);

CREATE TABLE validation_results (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id  uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  passed      boolean NOT NULL,
  failures    jsonb NOT NULL DEFAULT '[]',          -- Pandera failure cases (capped)
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dashboards (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id   uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  version_id   uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  spec_version text  NOT NULL,
  spec         jsonb NOT NULL,                      -- validated chart spec
  computed     jsonb NOT NULL DEFAULT '{}',         -- cached query results + KPI values
  narrative    jsonb NOT NULL DEFAULT '[]',         -- validated, placeholder-bound
  share_token  text UNIQUE,                         -- v1.1
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (version_id)
);
CREATE TRIGGER trg_dashboards_updated BEFORE UPDATE ON dashboards FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE exports (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id  uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  version_id  uuid NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
  kind        export_kind NOT NULL,
  storage_key text NOT NULL,
  sha256      char(64) NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz
);
CREATE INDEX ix_exports_dataset ON exports(dataset_id);

CREATE TABLE jobs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id     uuid REFERENCES datasets(id) ON DELETE CASCADE,
  owner_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type           job_type NOT NULL,
  status         job_status NOT NULL DEFAULT 'queued',
  progress       smallint NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  celery_task_id text,
  idempotency_key text,
  payload        jsonb NOT NULL DEFAULT '{}',
  result         jsonb,
  error          jsonb,                              -- {code, message, details}
  attempts       smallint NOT NULL DEFAULT 0,
  started_at     timestamptz,
  finished_at    timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_id, idempotency_key)
);
CREATE INDEX ix_jobs_dataset ON jobs(dataset_id, created_at DESC);
CREATE INDEX ix_jobs_active ON jobs(status) WHERE status IN ('queued','running');

CREATE TABLE llm_calls (       -- never stores raw cell values
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id    uuid REFERENCES datasets(id) ON DELETE SET NULL,
  job_id        uuid REFERENCES jobs(id) ON DELETE SET NULL,
  purpose       text NOT NULL CHECK (purpose IN ('semantics','proposals','chart_spec','narrative','ask')),
  provider      text NOT NULL,
  model         text NOT NULL,
  prompt_version text NOT NULL,
  input_hash    char(64) NOT NULL,                   -- cache key (schema + masked sample + prompt version)
  input_tokens  integer,
  output_tokens integer,
  latency_ms    integer,
  cache_hit     boolean NOT NULL DEFAULT false,
  valid_output  boolean,
  error         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_llm_calls_cache ON llm_calls(input_hash, prompt_version);

CREATE TABLE audit_log (
  id         bigserial PRIMARY KEY,
  user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  dataset_id uuid,
  action     text NOT NULL,                          -- e.g. 'proposal.accept','dataset.delete','export.create'
  detail     jsonb NOT NULL DEFAULT '{}',
  ip         inet,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_dataset ON audit_log(dataset_id, created_at DESC);
