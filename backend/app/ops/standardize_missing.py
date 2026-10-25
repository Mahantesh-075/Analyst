"""Standardize missing operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class StandardizeMissingParams(BaseModel):
    columns: list[str] = Field(..., min_length=1)
    tokens: list[str] = Field(..., min_length=1)


class StandardizeMissingOp(BaseOp):
    name: ClassVar[str] = "standardize_missing"

    def __init__(self, columns: list[str], tokens: list[str]) -> None:
        self.params = StandardizeMissingParams(columns=columns, tokens=tokens)
        self.columns = self.params.columns
        self.tokens = self.params.tokens

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        exprs = []
        for c in self.columns:
            # Match token when trimmed or exact
            expr = (
                pl.when(
                    pl.col(c).cast(pl.String).str.strip_chars().is_in(self.tokens)
                    | pl.col(c).cast(pl.String).is_in(self.tokens)
                )
                .then(None)
                .otherwise(pl.col(c))
                .alias(c)
            )
            exprs.append(expr)
        return lf.with_columns(exprs)

    def to_python(self, df_var: str = "df") -> str:
        tokens_repr = repr(self.tokens)
        exprs = []
        for c in self.columns:
            exprs.append(
                f"pl.when(pl.col({c!r}).cast(pl.String).str.strip_chars().is_in({tokens_repr}) | "
                f"pl.col({c!r}).cast(pl.String).is_in({tokens_repr})).then(None).otherwise(pl.col({c!r})).alias({c!r})"
            )
        return f"{df_var} = {df_var}.with_columns([{', '.join(exprs)}])"

    def to_sql(self, input_table: str, output_table: str) -> str:
        exclude_cols = ", ".join(f'"{c}"' for c in self.columns)
        escaped_tokens = ", ".join("'" + tok.replace("'", "''") + "'" for tok in self.tokens)
        exprs = []
        for c in self.columns:
            exprs.append(
                f'CASE WHEN TRIM(CAST("{c}" AS VARCHAR)) IN ({escaped_tokens}) OR CAST("{c}" AS VARCHAR) IN ({escaped_tokens}) '
                f'THEN NULL ELSE "{c}" END AS "{c}"'
            )
        return f'{output_table} AS (SELECT * EXCLUDE ({exclude_cols}), {", ".join(exprs)} FROM {input_table})'
