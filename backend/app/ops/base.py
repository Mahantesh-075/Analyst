"""Base class and protocol for unified data transformation operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import polars as pl
from pydantic import BaseModel, ConfigDict


class OpImpact(BaseModel):
    """Impact summary of a transformation operation."""

    model_config = ConfigDict(extra="forbid")

    rows_before: int
    rows_after: int
    cells_modified: int
    sample_before: list[dict[str, Any]]
    sample_after: list[dict[str, Any]]


class BaseOp(ABC):
    """Abstract base class for all registered transform operations."""

    name: ClassVar[str]

    @abstractmethod
    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Execute operation lazily using Polars."""
        ...

    @abstractmethod
    def to_python(self, df_var: str = "df") -> str:
        """Generate standalone Python code string mutating or reassigning `df_var`."""
        ...

    @abstractmethod
    def to_sql(self, input_table: str, output_table: str) -> str:
        """Generate DuckDB SQL CTE string producing `output_table` from `input_table`."""
        ...

    def preview(self, df: pl.DataFrame, n_rows: int = 5) -> dict[str, Any]:
        """Compute impact statistics and sample before/after rows deterministically."""
        rows_before = df.height
        out_df = self.apply(df.lazy()).collect()
        rows_after = out_df.height

        sample_before: list[dict[str, Any]] = []
        sample_after: list[dict[str, Any]] = []
        cells_modified = 0

        if rows_before == rows_after and set(df.columns) == set(out_df.columns):
            # Check cell-level differences
            changed_mask = pl.Series("mask", [False] * df.height)
            for col in df.columns:
                diff_expr = (df[col].is_not_null() & out_df[col].is_null()) | \
                            (df[col].is_null() & out_df[col].is_not_null()) | \
                            ((df[col].is_not_null() & out_df[col].is_not_null()) & (df[col].cast(pl.String) != out_df[col].cast(pl.String)))
                cells_modified += int(diff_expr.sum() or 0)
                changed_mask = changed_mask | diff_expr

            changed_indices = [i for i, ch in enumerate(changed_mask.to_list()) if ch]
            sample_indices = changed_indices[:n_rows] if changed_indices else list(range(min(n_rows, df.height)))
            sample_before = [df[i].to_dicts()[0] for i in sample_indices] if sample_indices else []
            sample_after = [out_df[i].to_dicts()[0] for i in sample_indices] if sample_indices else []
        elif rows_after != rows_before:
            cells_modified = abs(rows_before - rows_after) * len(df.columns)
            sample_before = df.head(n_rows).to_dicts()
            sample_after = out_df.head(n_rows).to_dicts()
        else:
            # Columns changed (e.g. rename, drop, split)
            cells_modified = rows_before
            sample_before = df.head(n_rows).to_dicts()
            sample_after = out_df.head(n_rows).to_dicts()

        return {
            "rows_before": rows_before,
            "rows_after": rows_after,
            "cells_modified": cells_modified,
            "sample_before": sample_before,
            "sample_after": sample_after,
        }
