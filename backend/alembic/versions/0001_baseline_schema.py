"""baseline_schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-25 12:00:00.000000

"""
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # If tables already exist (e.g. initial setup from db/schema.sql), skip DDL creation
    if "users" in existing_tables and "datasets" in existing_tables:
        return

    # Read schema.sql from the repository root db/schema.sql
    schema_path = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
    if not schema_path.exists():
        schema_path = Path("/app/db/schema.sql")
    if not schema_path.exists():
        schema_path = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

    with open(schema_path, encoding="utf-8") as f:
        schema_sql = f.read()

    # Execute individual statements
    statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
    for stmt in statements:
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    tables = [
        "audit_log",
        "llm_calls",
        "jobs",
        "exports",
        "dashboards",
        "validation_results",
        "transform_steps",
        "cleaning_proposals",
        "column_profiles",
        "profiles",
        "dataset_versions",
        "datasets",
        "refresh_tokens",
        "users",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

    enums = [
        "export_kind",
        "job_status",
        "job_type",
        "severity_level",
        "proposal_status",
        "proposal_source",
        "version_kind",
        "dataset_status",
    ]
    for enum in enums:
        op.execute(f"DROP TYPE IF EXISTS {enum} CASCADE;")

    op.execute("DROP FUNCTION IF EXISTS forbid_version_update() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")
