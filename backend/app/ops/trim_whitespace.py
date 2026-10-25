"""Trim whitespace operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class TrimWhitespaceParams(BaseModel):
    columns: list[str] = Field(..., min_length=1)


class TrimWhitespaceOp(BaseOp):
    name: ClassVar[str] = "trim_whitespace"

    def __init__(self, columns: list[str]) -> None:
        self.params = TrimWhitespaceParams(columns=columns)
        self.columns = self.params.columns

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.with_columns(
            [pl.col(c).cast(pl.String).str.strip_chars().alias(c) for c in self.columns]
        )

    def to_python(self, df_var: str = "df") -> str:
        exprs = ", ".join(f"pl.col({c!r}).cast(pl.String).str.strip_chars().alias({c!r})" for c in self.columns)
        return f"{df_var} = {df_var}.with_columns([{exprs}])"

    def to_sql(self, input_table: str, output_table: str) -> str:
        exclude_cols = ", ".join(f'"{c}"' for c in self.columns)
        trim_exprs = ", ".join(f'TRIM(CAST("{c}" AS VARCHAR)) AS "{c}"' for c in self.columns)
        return f'{output_table} AS (SELECT * EXCLUDE ({exclude_cols}), {trim_exprs} FROM {input_table})'
