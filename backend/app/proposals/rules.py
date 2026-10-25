"""Deterministic proposal generation rules engine."""

from __future__ import annotations

from typing import Any

import polars as pl

from app.db.models.profile import ColumnProfile, Profile
from app.ops.registry import get_op


def generate_rule_proposals(
    dataset_profile: Profile,
    column_profiles: list[ColumnProfile],
    sample_df: pl.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Deterministically analyze dataset profile and anomalies to generate transform proposals."""
    proposals: list[dict[str, Any]] = []

    # 1. Check exact duplicate rows
    summary = dataset_profile.summary or {}
    dup_rows = summary.get("duplicate_row_count", 0)
    if dup_rows > 0:
        op_obj = get_op("drop_duplicates", {"keep": "first"})
        preview = op_obj.preview(sample_df) if sample_df is not None else {}
        proposals.append({
            "op": "drop_duplicates",
            "params": {"keep": "first"},
            "target_columns": [],
            "reason": f"Detected {dup_rows} duplicate rows across dataset. Deduplication preserves unique observations.",
            "severity": "medium",
            "source": "rule",
            "confidence": 0.98,
            "impact_preview": preview,
        })

    # 2. Check whitespace across string columns
    str_cols_with_ws: list[str] = []
    for col in column_profiles:
        if col.inferred_dtype in ("String", "Utf8", "str") or "str" in col.inferred_dtype.lower():
            stats = col.stats or {}
            if stats.get("has_whitespace", False) or stats.get("min_len", 0) > 0:
                str_cols_with_ws.append(col.name)

    if str_cols_with_ws:
        trim_params: dict[str, Any] = {"columns": str_cols_with_ws}
        op_obj = get_op("trim_whitespace", trim_params)
        preview = op_obj.preview(sample_df) if sample_df is not None else {}
        proposals.append({
            "op": "trim_whitespace",
            "params": trim_params,
            "target_columns": str_cols_with_ws,
            "reason": f"Strip leading, trailing, and redundant whitespace across {len(str_cols_with_ws)} text column(s).",
            "severity": "low",
            "source": "rule",
            "confidence": 0.95,
            "impact_preview": preview,
        })

    # 3. Check missing tokens across columns
    for col in column_profiles:
        if col.missing_tokens:
            std_params: dict[str, Any] = {"columns": [col.name], "tokens": list(col.missing_tokens)}
            op_obj = get_op("standardize_missing", std_params)
            preview = op_obj.preview(sample_df) if sample_df is not None else {}
            proposals.append({
                "op": "standardize_missing",
                "params": std_params,
                "target_columns": [col.name],
                "reason": f"Column '{col.name}' contains sentinel missing tokens: {col.missing_tokens}. Standardize to true nulls.",
                "severity": "medium",
                "source": "rule",
                "confidence": 0.96,
                "impact_preview": preview,
            })

    # 4. Check PII masking
    for col in column_profiles:
        if col.is_pii:
            pii_list = ", ".join(col.pii_types)
            pii_params: dict[str, Any] = {"column": col.name, "method": "redact"}
            op_obj = get_op("mask_pii", pii_params)
            preview = op_obj.preview(sample_df) if sample_df is not None else {}
            proposals.append({
                "op": "mask_pii",
                "params": pii_params,
                "target_columns": [col.name],
                "reason": f"Column '{col.name}' contains sensitive PII types ({pii_list}). Mask values to prevent exposure.",
                "severity": "high",
                "source": "rule",
                "confidence": 0.99,
                "impact_preview": preview,
            })

    # 5. Check outlier handling on numeric columns
    for col in column_profiles:
        stats = col.stats or {}
        outlier_count = stats.get("outliers_iqr_count", 0)
        if outlier_count > 0:
            outlier_params: dict[str, Any] = {"column": col.name, "method": "iqr", "threshold": 1.5, "action": "clip"}
            op_obj = get_op("handle_outliers", outlier_params)
            preview = op_obj.preview(sample_df) if sample_df is not None else {}
            proposals.append({
                "op": "handle_outliers",
                "params": outlier_params,
                "target_columns": [col.name],
                "reason": f"Column '{col.name}' has {outlier_count} severe statistical outliers beyond 1.5x IQR. Clip to robust bounds.",
                "severity": "medium",
                "source": "rule",
                "confidence": 0.90,
                "impact_preview": preview,
            })

    # 6. Check high-confidence date strings
    for col in column_profiles:
        stats = col.stats or {}
        if stats.get("inferred_date_format"):
            fmt = stats["inferred_date_format"]
            date_params: dict[str, Any] = {"column": col.name, "format": fmt}
            op_obj = get_op("parse_date", date_params)
            preview = op_obj.preview(sample_df) if sample_df is not None else {}
            proposals.append({
                "op": "parse_date",
                "params": date_params,
                "target_columns": [col.name],
                "reason": f"Column '{col.name}' matches date pattern '{fmt}'. Parse string values into native Date.",
                "severity": "medium",
                "source": "rule",
                "confidence": 0.93,
                "impact_preview": preview,
            })

    # 7. Check null imputation
    for col in column_profiles:
        if 0 < col.null_pct <= 0.30:
            stats = col.stats or {}
            if "mean" in stats and stats["mean"] is not None:
                impute_params: dict[str, Any] = {"column": col.name, "strategy": "median"}
                op_obj = get_op("impute", impute_params)
                preview = op_obj.preview(sample_df) if sample_df is not None else {}
                proposals.append({
                    "op": "impute",
                    "params": impute_params,
                    "target_columns": [col.name],
                    "reason": f"Column '{col.name}' has {col.null_pct * 100:.1f}% missing values. Impute using median.",
                    "severity": "low",
                    "source": "rule",
                    "confidence": 0.88,
                    "impact_preview": preview,
                })

    return proposals
