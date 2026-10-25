"""Unit tests for Safe DuckDB Query Builder and Deterministic Narrative Validator (Invariant 3 & 5)."""

from __future__ import annotations

import io

import polars as pl
import pytest

from app.dashboard.narratives import (
    InvariantViolationError,
    render_narrative,
    validate_narrative_template,
)
from app.dashboard.query_builder import SafeQueryError, build_sql, execute_safe_query


def test_narrative_template_invariant_3_enforcement() -> None:
    allowed_refs = {"total_records", "avg_salary"}

    # Valid template: no digits outside {{placeholder}}
    template_valid = "There are {{total_records}} verified employees with an average salary of {{avg_salary}}."
    refs = validate_narrative_template(template_valid, allowed_refs)
    assert refs == ["total_records", "avg_salary"]

    # Invariant 3 Violation: literal digit outside placeholder
    template_invalid_digit = "There are 42 records found for {{total_records}}."
    with pytest.raises(InvariantViolationError) as exc_info:
        validate_narrative_template(template_invalid_digit, allowed_refs)
    assert "Invariant 3 Violation" in str(exc_info.value)
    assert "4" in str(exc_info.value)

    # Invariant Violation: unknown reference
    template_unknown_ref = "Data has {{unknown_metric}} entries."
    with pytest.raises(InvariantViolationError) as exc_info:
        validate_narrative_template(template_unknown_ref, allowed_refs)
    assert "unknown_metric" in str(exc_info.value)


def test_narrative_rendering() -> None:
    template = "Total count is {{total_records}} with mean {{avg_salary}} and growth of {{growth_rate}}."
    values = {"total_records": 15000, "avg_salary": 92500.5, "growth_rate": 0.125}
    formats = {"total_records": "integer", "avg_salary": "currency", "growth_rate": "percent"}

    rendered = render_narrative(template, values, formats)
    assert "Total count is 15,000" in rendered
    assert "with mean $92,500.50" in rendered
    assert "and growth of 12.5%." in rendered


def test_query_builder_allowlisting_and_sql_construction() -> None:
    allowed_cols = {"department", "salary", "join_date", "status"}

    query_spec = {
        "dimensions": [{"field": "department"}],
        "measures": [
            {"field": "*", "agg": "count", "as": "emp_count"},
            {"field": "salary", "agg": "mean", "as": "avg_salary"},
        ],
        "filters": [
            {"field": "status", "op": "eq", "value": "active"},
            {"field": "salary", "op": "between", "value": [30000, 150000]},
        ],
        "order_by": [{"field": "emp_count", "dir": "desc"}],
        "limit": 10,
    }

    sql, params = build_sql(query_spec, "table_source", allowed_cols)
    assert 'COUNT(*) AS "emp_count"' in sql
    assert 'AVG("salary") AS "avg_salary"' in sql
    assert '"department"' in sql
    assert '"status" = ?' in sql
    assert '"salary" BETWEEN ? AND ?' in sql
    assert params == ["active", 30000, 150000]

    # Malicious injection attempt in column name
    bad_spec = {
        "dimensions": [{"field": "department; DROP TABLE users;"}],
        "measures": [{"field": "*", "agg": "count", "as": "cnt"}],
    }
    with pytest.raises(SafeQueryError) as exc_info:
        build_sql(bad_spec, "table_source", allowed_cols)
    assert "Unauthorized column" in str(exc_info.value)


def test_execute_safe_query_on_parquet() -> None:
    df = pl.DataFrame({
        "dept": ["Engineering", "Engineering", "Sales", "HR"],
        "salary": [100000.0, 120000.0, 80000.0, 70000.0],
    })
    buf = io.BytesIO()
    df.write_parquet(buf)
    parquet_bytes = buf.getvalue()

    allowed = {"dept", "salary"}
    query_spec = {
        "dimensions": [{"field": "dept"}],
        "measures": [
            {"field": "*", "agg": "count", "as": "count"},
            {"field": "salary", "agg": "mean", "as": "avg_salary"},
        ],
        "order_by": [{"field": "count", "dir": "desc"}],
        "limit": 5,
    }

    res = execute_safe_query(parquet_bytes, query_spec, allowed)
    assert res["row_count"] == 3
    assert res["columns"] == ["dept", "count", "avg_salary"]
    eng_row = next(r for r in res["rows"] if r["dept"] == "Engineering")
    assert eng_row["count"] == 2
    assert eng_row["avg_salary"] == 110000.0
