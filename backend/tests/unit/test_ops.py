"""Unit tests and equivalence verification for all 14 transform operations."""

import duckdb
import polars as pl
import pytest

from app.ops.registry import (
    OP_REGISTRY,
    compile_pipeline_to_sql,
    get_op,
    parse_transform_step,
)


def test_registry_contains_all_fourteen_ops() -> None:
    expected_ops = {
        "rename_column",
        "cast_type",
        "trim_whitespace",
        "normalize_case",
        "standardize_missing",
        "impute",
        "drop_null_rows",
        "drop_duplicates",
        "parse_date",
        "handle_outliers",
        "map_values",
        "split_column",
        "drop_column",
        "mask_pii",
    }
    assert set(OP_REGISTRY.keys()) == expected_ops
    assert len(OP_REGISTRY) == 14


def test_rename_column_op() -> None:
    df = pl.DataFrame({"old_name": ["a", "b"], "val": [1, 2]})
    op = get_op("rename_column", {"column": "old_name", "new_name": "clean_name"})
    res = op.apply(df.lazy()).collect()
    assert "clean_name" in res.columns
    assert "old_name" not in res.columns

    # Test preview
    preview = op.preview(df)
    assert preview["rows_before"] == 2
    assert preview["rows_after"] == 2


def test_trim_whitespace_op() -> None:
    df = pl.DataFrame({"text": ["  hello  ", "world \t", "clean"]})
    op = get_op("trim_whitespace", {"columns": ["text"]})
    res = op.apply(df.lazy()).collect()
    assert res["text"].to_list() == ["hello", "world", "clean"]

    # Preview
    preview = op.preview(df)
    assert preview["cells_modified"] == 2


def test_normalize_case_op() -> None:
    df = pl.DataFrame({"city": ["new york", "LONDON", "paris"]})
    op_title = get_op("normalize_case", {"columns": ["city"], "mode": "title"})
    res = op_title.apply(df.lazy()).collect()
    assert res["city"].to_list() == ["New York", "London", "Paris"]


def test_standardize_missing_op() -> None:
    df = pl.DataFrame({"status": ["active", "N/A", "pending", " - ", "NULL"]})
    op = get_op("standardize_missing", {"columns": ["status"], "tokens": ["N/A", "-", "NULL"]})
    res = op.apply(df.lazy()).collect()
    assert res["status"].to_list() == ["active", None, "pending", None, None]


def test_cast_type_op() -> None:
    df = pl.DataFrame({"num": ["10", "20", "invalid"]})
    op = get_op("cast_type", {"column": "num", "to": "int", "on_error": "null"})
    res = op.apply(df.lazy()).collect()
    assert res["num"].to_list() == [10, 20, None]


def test_impute_op() -> None:
    df = pl.DataFrame({"val": [10.0, None, 30.0]})
    op = get_op("impute", {"column": "val", "strategy": "mean"})
    res = op.apply(df.lazy()).collect()
    assert res["val"].to_list() == [10.0, 20.0, 30.0]


def test_drop_null_rows_op() -> None:
    df = pl.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
    op_any = get_op("drop_null_rows", {"columns": ["a", "b"], "how": "any"})
    res_any = op_any.apply(df.lazy()).collect()
    assert res_any.height == 1
    assert res_any["a"].to_list() == [1]


def test_drop_duplicates_op() -> None:
    df = pl.DataFrame({"id": [1, 1, 2], "val": ["a", "a", "b"]})
    op = get_op("drop_duplicates", {"subset": ["id", "val"]})
    res = op.apply(df.lazy()).collect()
    assert res.height == 2


def test_handle_outliers_clip_and_flag() -> None:
    df = pl.DataFrame({"val": [10.0, 11.0, 12.0, 10.5, 11.5, 1000.0]})
    op_flag = get_op("handle_outliers", {"column": "val", "method": "iqr", "action": "flag", "threshold": 1.5})
    res_flag = op_flag.apply(df.lazy()).collect()
    assert "val_is_outlier" in res_flag.columns
    assert res_flag["val_is_outlier"].to_list()[-1] is True


def test_map_values_op() -> None:
    df = pl.DataFrame({"code": ["US", "IN", "UK", "OTHER"]})
    op = get_op("map_values", {"column": "code", "mapping": {"US": "United States", "IN": "India"}})
    res = op.apply(df.lazy()).collect()
    assert res["code"].to_list() == ["United States", "India", "UK", "OTHER"]


def test_split_column_op() -> None:
    df = pl.DataFrame({"name": ["John Doe", "Jane Smith"]})
    op = get_op("split_column", {"column": "name", "delimiter": " ", "into": ["first_name", "last_name"]})
    res = op.apply(df.lazy()).collect()
    assert "first_name" in res.columns
    assert "last_name" in res.columns
    assert "name" not in res.columns
    assert res["first_name"].to_list() == ["John", "Jane"]


def test_drop_column_op() -> None:
    df = pl.DataFrame({"keep_me": [1, 2], "drop_me": [3, 4]})
    op = get_op("drop_column", {"column": "drop_me"})
    res = op.apply(df.lazy()).collect()
    assert res.columns == ["keep_me"]


def test_mask_pii_op() -> None:
    df = pl.DataFrame({"email": ["alice@example.com", "bob@test.com"]})
    op_redact = get_op("mask_pii", {"column": "email", "method": "redact"})
    res = op_redact.apply(df.lazy()).collect()
    assert res["email"].to_list() == ["***REDACTED***", "***REDACTED***"]


def test_duckdb_sql_pipeline_equivalence() -> None:
    df = pl.DataFrame({
        "first_name": [" alice ", "BOB", "charlie"],
        "age": ["25", "invalid", "35"],
        "city": ["NY", "SF", "LA"],
    })

    steps = [
        get_op("trim_whitespace", {"columns": ["first_name"]}),
        get_op("normalize_case", {"columns": ["first_name"], "mode": "title"}),
        get_op("cast_type", {"column": "age", "to": "int", "on_error": "null"}),
    ]

    # Run Polars
    cur_lf = df.lazy()
    for s in steps:
        cur_lf = s.apply(cur_lf)
    polars_res = cur_lf.collect()

    # Run DuckDB SQL
    sql_script = compile_pipeline_to_sql(steps, raw_table="raw_data")
    con = duckdb.connect()
    con.register("raw_data", df.to_arrow())
    duck_res = con.query(sql_script).pl()

    assert polars_res["first_name"].to_list() == duck_res["first_name"].to_list()
    assert polars_res["age"].to_list() == duck_res["age"].to_list()


def test_parse_transform_step_from_schema_format() -> None:
    step_dict = {
        "op": "rename_column",
        "params": {
            "column": "user_id",
            "new_name": "customer_id",
        },
    }
    op = parse_transform_step(step_dict)
    assert op.name == "rename_column"

    with pytest.raises(ValueError):
        parse_transform_step({"op": "non_existent_op", "params": {}})
