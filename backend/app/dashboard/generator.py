"""Deterministic dashboard and visualization generator conforming to schemas/chart_spec.schema.json."""

from __future__ import annotations

import io
from typing import Any

import polars as pl

from app.core.json_utils import sanitize_for_json
from app.dashboard.narratives import validate_narrative_template
from app.dashboard.query_builder import execute_safe_query


def build_vega_spec(chart: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compile a deterministic Vega-Lite v5 specification with embedded data values."""
    chart_type = chart.get("type", "bar")
    title = chart.get("title", "Visualization")
    encoding = chart.get("encoding", {})
    x_field = encoding.get("x", "")
    y_field = encoding.get("y", "")

    if rows and isinstance(rows[0], dict):
        keys = list(rows[0].keys())
        if not x_field or x_field not in keys:
            x_field = keys[0] if len(keys) > 0 else "x"
        if not y_field or y_field not in keys:
            y_field = keys[1] if len(keys) > 1 else keys[0]

    is_temporal = any(kw in str(x_field).lower() for kw in ("date", "time", "year", "month", "day"))
    x_type = "temporal" if is_temporal else ("nominal" if chart_type == "bar" else "ordinal")

    mark: dict[str, Any] = {
        "type": "bar",
        "tooltip": True,
        "cornerRadiusTopLeft": 4,
        "cornerRadiusTopRight": 4,
        "color": "#38bdf8",
    } if chart_type == "bar" else {
        "type": "line",
        "point": True,
        "tooltip": True,
        "color": "#6366f1",
    }

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {
            "text": title,
            "anchor": "start",
            "fontSize": 13,
            "fontWeight": 600,
        },
        "width": "container",
        "height": 260,
        "data": {
            "values": rows,
        },
        "mark": mark,
        "encoding": {
            "x": {
                "field": x_field,
                "type": x_type,
                "axis": {"labelAngle": -30, "title": x_field, "labelLimit": 120},
            },
            "y": {
                "field": y_field,
                "type": "quantitative",
                "axis": {"title": y_field},
            },
        },
    }


def generate_dashboard_spec(
    dataset_name: str,
    column_profiles: list[dict[str, Any]],
    total_rows: int,
) -> dict[str, Any]:
    """Generate a valid, deterministic DashboardSpec conforming strictly to schemas/chart_spec.schema.json."""
    kpis: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    narratives: list[dict[str, Any]] = []

    # 1. Base KPI: Total records
    kpis.append({
        "id": "total_records",
        "label": "Total Records",
        "measure": {"field": "*", "agg": "count"},
        "format": "integer",
    })

    # Find numeric, categorical, and date columns
    numeric_cols: list[dict[str, Any]] = []
    categorical_cols: list[dict[str, Any]] = []
    date_cols: list[dict[str, Any]] = []

    for col in column_profiles:
        dtype = col.get("inferred_dtype", "").lower()
        stats = col.get("stats") or {}
        name = col["name"]
        clean_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        if not clean_name or not clean_name[0].isalpha():
            clean_name = f"c_{clean_name}"
        clean_name = clean_name[:35]

        if any(num_t in dtype for num_t in ("int", "float", "decimal", "double")):
            numeric_cols.append({**col, "clean_id": clean_name})
        elif "date" in dtype or "time" in dtype or stats.get("date_info", {}).get("is_date"):
            date_cols.append({**col, "clean_id": clean_name})
        else:
            categorical_cols.append({**col, "clean_id": clean_name})

    # Add numeric KPIs (up to 5 more)
    for col in numeric_cols[:2]:
        cid = col["clean_id"]
        col_name = col["name"]
        kpis.append({
            "id": f"avg_{cid}",
            "label": f"Average {col_name}",
            "measure": {"field": col_name, "agg": "mean"},
            "format": "decimal",
        })
        kpis.append({
            "id": f"max_{cid}",
            "label": f"Max {col_name}",
            "measure": {"field": col_name, "agg": "max"},
            "format": "decimal",
        })

    # Ensure max 6 KPIs
    kpis = kpis[:6]
    allowed_kpi_ids = {k["id"] for k in kpis}

    # Generate Charts (up to 12)
    chart_idx = 1

    # Categorical breakdown (bar chart)
    for col in categorical_cols[:3]:
        col_name = col["name"]
        cid = col["clean_id"]
        chart_id = f"chart_{chart_idx}_{cid}_dist"
        charts.append({
            "id": chart_id[:40],
            "type": "bar",
            "title": f"Distribution by {col_name}",
            "query": {
                "dimensions": [{"field": col_name}],
                "measures": [{"field": "*", "agg": "count", "as": "record_count"}],
                "order_by": [{"field": "record_count", "dir": "desc"}],
                "limit": 20,
            },
            "encoding": {"x": col_name, "y": "record_count"},
            "rationale": f"Shows distribution of records across categories in {col_name}."[:200],
        })
        chart_idx += 1

    # Numeric breakdown (histogram or box)
    for col in numeric_cols[:3]:
        col_name = col["name"]
        cid = col["clean_id"]
        chart_id = f"chart_{chart_idx}_{cid}_summary"
        charts.append({
            "id": chart_id[:40],
            "type": "bar",
            "title": f"Metrics for {col_name}",
            "query": {
                "measures": [
                    {"field": col_name, "agg": "mean", "as": f"avg_{cid}"},
                    {"field": col_name, "agg": "median", "as": f"med_{cid}"},
                    {"field": col_name, "agg": "max", "as": f"max_{cid}"},
                ],
                "limit": 1,
            },
            "encoding": {"x": f"avg_{cid}", "y": f"max_{cid}"},
            "rationale": f"Key distribution statistics for numeric field {col_name}."[:200],
        })
        chart_idx += 1

    # Date trend (line chart)
    for col in date_cols[:2]:
        col_name = col["name"]
        cid = col["clean_id"]
        chart_id = f"chart_{chart_idx}_{cid}_trend"
        charts.append({
            "id": chart_id[:40],
            "type": "line",
            "title": f"Records Over Time ({col_name})",
            "query": {
                "dimensions": [{"field": col_name, "bucket": "month"}],
                "measures": [{"field": "*", "agg": "count", "as": "record_count"}],
                "order_by": [{"field": col_name, "dir": "asc"}],
                "limit": 50,
            },
            "encoding": {"x": col_name, "y": "record_count"},
            "rationale": f"Tracks monthly volume progression along date field {col_name}."[:200],
        })
        chart_idx += 1

    # If no charts yet, add a simple table/count chart
    if not charts and column_profiles:
        first_col = column_profiles[0]["name"]
        charts.append({
            "id": "chart_record_count",
            "type": "bar",
            "title": "Dataset Volume Summary",
            "query": {
                "dimensions": [{"field": first_col}],
                "measures": [{"field": "*", "agg": "count", "as": "total_count"}],
                "limit": 10,
            },
            "encoding": {"x": first_col, "y": "total_count"},
            "rationale": "High-level record count summary by primary attribute.",
        })

    # Generate Narratives strictly adhering to Invariant 3 (no digits outside {{ref}})
    narratives.append({
        "template": "Dataset analysis successfully indexed {{total_records}} verified records across clean dimensions.",
        "refs": ["total_records"],
    })

    if len(numeric_cols) > 0 and len(kpis) > 1:
        first_num = numeric_cols[0]
        cid = first_num["clean_id"]
        if f"avg_{cid}" in allowed_kpi_ids:
            narratives.append({
                "template": f"The mean metric value across verified observations is measured at {{avg_{cid}}}.",
                "refs": [f"avg_{cid}"],
            })

    # Validate each narrative item against Invariant 3
    for n in narratives:
        validate_narrative_template(n["template"], allowed_kpi_ids)

    return {
        "spec_version": "1.0",
        "title": f"{dataset_name} Analytics Dashboard"[:120],
        "kpis": kpis,
        "charts": charts,
        "narrative": narratives,
    }


def compute_dashboard_data(
    spec: dict[str, Any],
    parquet_bytes: bytes,
    allowed_columns: set[str],
) -> dict[str, Any]:
    """Execute all KPI and chart queries against Parquet bytes to produce live data."""
    df = pl.read_parquet(io.BytesIO(parquet_bytes))

    # 1. Compute KPIs
    computed_kpis: list[dict[str, Any]] = []
    kpi_values_map: dict[str, Any] = {}

    for kpi in spec.get("kpis", []):
        kid = kpi["id"]
        measure = kpi["measure"]
        field = measure.get("field")
        agg = measure.get("agg")

        val: Any = None
        if field == "*" or agg == "count":
            val = df.height
        elif field and field in df.columns:
            series = df[field]
            if agg == "count_distinct":
                val = series.n_unique()
            elif agg == "mean":
                val = series.mean()
            elif agg == "median":
                val = series.median()
            elif agg == "sum":
                val = series.sum()
            elif agg == "min":
                val = series.min()
            elif agg == "max":
                val = series.max()

        if isinstance(val, (float,)) and (val != val):  # NaN check
            val = None

        computed_kpis.append({
            **kpi,
            "computed_value": val,
        })
        kpi_values_map[kid] = val

    # 2. Compute Chart Queries
    computed_charts: list[dict[str, Any]] = []
    for chart in spec.get("charts", []):
        query_spec = chart.get("query", {})
        try:
            query_res = execute_safe_query(parquet_bytes, query_spec, allowed_columns)
        except Exception:
            query_res = {"columns": [], "rows": [], "row_count": 0}

        sanitized_rows = sanitize_for_json(query_res.get("rows", []))
        sanitized_data = {
            "columns": query_res.get("columns", []),
            "rows": sanitized_rows,
            "row_count": len(sanitized_rows),
        }
        vega_spec = build_vega_spec(chart, sanitized_rows)

        computed_charts.append({
            **chart,
            "data": sanitized_data,
            "vega_spec": vega_spec,
        })

    return {
        "spec": spec,
        "kpis": sanitize_for_json(computed_kpis),
        "charts": computed_charts,
        "kpi_values": sanitize_for_json(kpi_values_map),
    }
