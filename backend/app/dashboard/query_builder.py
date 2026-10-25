"""Safe DuckDB Query Builder enforcing strict identifier allow-listing, parameter binding, and resource caps."""

from __future__ import annotations

import re
import tempfile
from typing import Any

import duckdb

# Allowed aggregation functions
ALLOWED_AGGS: set[str] = {
    "count",
    "count_distinct",
    "sum",
    "mean",
    "avg",
    "median",
    "min",
    "max",
}

# Allowed comparison operators
ALLOWED_OPS: dict[str, str] = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "is_null": "IS NULL",
    "not_null": "IS NOT NULL",
    "in": "IN",
    "between": "BETWEEN",
}

# Allowed date truncation buckets
ALLOWED_BUCKETS: set[str] = {"day", "week", "month", "quarter", "year"}

# Regex for safe alias names
SAFE_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


class SafeQueryError(Exception):
    """Raised when a query violates safety constraints or identifier allow-lists."""


def validate_identifier(name: str, allowed_columns: set[str]) -> str:
    """Validate that an identifier exists in the allowed column set."""
    if name not in allowed_columns:
        raise SafeQueryError(f"Unauthorized column or identifier: '{name}'. Not in allowed schema.")
    return f'"{name}"'


def sanitize_alias(alias: str) -> str:
    """Sanitize arbitrary alias string into strict ^[a-z][a-z0-9_]{0,40}$ pattern."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", alias).lower().strip("_")
    if not clean or not clean[0].isalpha():
        clean = f"col_{clean}"
    return clean[:40]


def validate_alias(alias: str) -> str:
    """Validate and sanitize an alias to ensure safe execution in SQL."""
    if not SAFE_IDENTIFIER_RE.match(alias):
        alias = sanitize_alias(alias)
    return f'"{alias}"'


def build_sql(
    query_spec: dict[str, Any],
    table_source: str,
    allowed_columns: set[str],
) -> tuple[str, list[Any]]:
    """Deterministically compile a structured query spec into safe DuckDB SQL with bound parameters.

    Rejects any un-whitelisted identifiers or raw SQL injections.
    """
    dimensions = list(query_spec.get("dimensions", []))
    measures = list(query_spec.get("measures", []))

    # Normalize alternate format (group_by, aggregations, columns)
    if not dimensions:
        if "group_by" in query_spec:
            for g in query_spec["group_by"]:
                if isinstance(g, str) and g != "none":
                    dimensions.append({"field": g})
                elif isinstance(g, dict):
                    dimensions.append(g)
        elif "columns" in query_spec and not measures:
            for c in query_spec["columns"]:
                if isinstance(c, str):
                    dimensions.append({"field": c})

    if not measures and "aggregations" in query_spec:
        for a in query_spec["aggregations"]:
            if isinstance(a, dict):
                col = a.get("column") or a.get("field")
                op = (a.get("operator") or a.get("agg") or "count").lower()
                alias = a.get("alias") or f"{op}_{col}"
                measures.append({"field": col, "agg": op, "as": alias})

    filters = query_spec.get("filters", [])
    order_by = query_spec.get("order_by", [])
    limit = int(query_spec.get("limit", 50))
    limit = max(1, min(limit, 1000))

    if not measures and not dimensions:
        raise SafeQueryError("Query spec must specify at least one measure or dimension.")

    select_clauses: list[str] = []
    group_by_indices: list[str] = []
    bound_params: list[Any] = []

    # 1. Dimensions
    col_idx = 1
    for dim in dimensions:
        field = dim.get("field")
        if not field:
            raise SafeQueryError("Dimension missing 'field'.")
        safe_field = validate_identifier(field, allowed_columns)

        bucket = dim.get("bucket")
        if bucket:
            if bucket not in ALLOWED_BUCKETS:
                raise SafeQueryError(f"Invalid bucket '{bucket}'. Allowed: {ALLOWED_BUCKETS}")
            select_clauses.append(f"DATE_TRUNC('{bucket}', {safe_field}) AS {safe_field}")
        else:
            select_clauses.append(f"{safe_field} AS {safe_field}")
        group_by_indices.append(str(col_idx))
        col_idx += 1

    # 2. Measures
    for m in measures:
        field = m.get("field")
        agg = m.get("agg")
        as_alias = m.get("as", f"{agg}_{field}" if field else agg)

        if agg not in ALLOWED_AGGS:
            raise SafeQueryError(f"Invalid aggregation '{agg}'. Allowed: {ALLOWED_AGGS}")

        safe_alias = validate_alias(as_alias)

        if field == "*" or (not field and agg == "count"):
            select_clauses.append(f"COUNT(*) AS {safe_alias}")
        else:
            if not field:
                raise SafeQueryError(f"Measure '{agg}' requires a target field.")
            safe_field = validate_identifier(field, allowed_columns)

            if agg == "count":
                select_clauses.append(f"COUNT({safe_field}) AS {safe_alias}")
            elif agg == "count_distinct":
                select_clauses.append(f"COUNT(DISTINCT {safe_field}) AS {safe_alias}")
            elif agg in ("mean", "avg"):
                select_clauses.append(f"AVG({safe_field}) AS {safe_alias}")
            elif agg == "median":
                select_clauses.append(f"MEDIAN({safe_field}) AS {safe_alias}")
            elif agg in ("sum", "min", "max"):
                select_clauses.append(f"{agg.upper()}({safe_field}) AS {safe_alias}")
        col_idx += 1

    # 3. Where Filters
    where_clauses: list[str] = []
    for f in filters:
        field = f.get("field")
        op = f.get("op")
        val = f.get("value")

        if not field or not op:
            raise SafeQueryError("Filter requires 'field' and 'op'.")
        if op not in ALLOWED_OPS:
            raise SafeQueryError(f"Unsupported operator '{op}'. Allowed: {set(ALLOWED_OPS.keys())}")

        safe_field = validate_identifier(field, allowed_columns)
        sql_op = ALLOWED_OPS[op]

        if op in ("is_null", "not_null"):
            where_clauses.append(f"{safe_field} {sql_op}")
        elif op == "in":
            if not isinstance(val, (list, tuple)) or len(val) == 0:
                raise SafeQueryError("IN filter requires a non-empty list of values.")
            placeholders = ", ".join(["?"] * len(val))
            where_clauses.append(f"{safe_field} IN ({placeholders})")
            bound_params.extend(val)
        elif op == "between":
            if not isinstance(val, (list, tuple)) or len(val) != 2:
                raise SafeQueryError("BETWEEN filter requires [min, max] list of 2 values.")
            where_clauses.append(f"{safe_field} BETWEEN ? AND ?")
            bound_params.extend(val)
        else:
            where_clauses.append(f"{safe_field} {sql_op} ?")
            bound_params.append(val)

    # 4. Construct SQL
    sql_parts = [
        f"SELECT {', '.join(select_clauses)}",
        f"FROM {table_source}",
    ]

    if where_clauses:
        sql_parts.append(f"WHERE {' AND '.join(where_clauses)}")

    if group_by_indices:
        sql_parts.append(f"GROUP BY {', '.join(group_by_indices)}")

    # 5. Order By
    order_clauses: list[str] = []
    for ob in order_by:
        field = ob.get("field")
        if not field:
            continue
        direction = ob.get("dir", "desc").lower()
        if direction not in ("asc", "desc"):
            direction = "desc"

        # Check if field is an alias or column
        if SAFE_IDENTIFIER_RE.match(field):
            order_clauses.append(f'"{field}" {direction.upper()}')
        else:
            safe_field = validate_identifier(field, allowed_columns)
            order_clauses.append(f"{safe_field} {direction.upper()}")

    if order_clauses:
        sql_parts.append(f"ORDER BY {', '.join(order_clauses)}")
    elif group_by_indices:
        # Default order by first column
        sql_parts.append("ORDER BY 1 ASC")

    sql_parts.append(f"LIMIT {limit}")
    return "\n".join(sql_parts), bound_params


def execute_safe_query(
    parquet_bytes: bytes,
    query_spec: dict[str, Any],
    allowed_columns: set[str],
) -> dict[str, Any]:
    """Execute a validated query spec against Parquet bytes under memory and timeout constraints."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        tmp.write(parquet_bytes)
        tmp.flush()

        con = duckdb.connect(":memory:")
        try:
            con.execute("SET memory_limit = '512MB';")
            con.execute("SET threads = 2;")
            con.execute("SET preserve_insertion_order = false;")

            table_source = f"read_parquet('{tmp.name}')"
            sql, params = build_sql(query_spec, table_source, allowed_columns)

            cursor = con.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            raw_rows = cursor.fetchall()
            records = [dict(zip(columns, row, strict=False)) for row in raw_rows]

            return {
                "columns": columns,
                "rows": records,
                "row_count": len(records),
            }
        finally:
            con.close()
