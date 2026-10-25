"""Normalize case operation."""

from __future__ import annotations

from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class NormalizeCaseParams(BaseModel):
    columns: list[str] = Field(..., min_length=1)
    mode: Literal["lower", "upper", "title"]


class NormalizeCaseOp(BaseOp):
    name: ClassVar[str] = "normalize_case"

    def __init__(self, columns: list[str], mode: Literal["lower", "upper", "title"]) -> None:
        self.params = NormalizeCaseParams(columns=columns, mode=mode)
        self.columns = self.params.columns
        self.mode = self.params.mode

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        exprs = []
        for c in self.columns:
            str_col = pl.col(c).cast(pl.String)
            if self.mode == "lower":
                exprs.append(str_col.str.to_lowercase().alias(c))
            elif self.mode == "upper":
                exprs.append(str_col.str.to_uppercase().alias(c))
            else:
                exprs.append(str_col.str.to_titlecase().alias(c))
        return lf.with_columns(exprs)

    def to_python(self, df_var: str = "df") -> str:
        method = "to_lowercase" if self.mode == "lower" else ("to_uppercase" if self.mode == "upper" else "to_titlecase")
        exprs = ", ".join(f"pl.col({c!r}).cast(pl.String).str.{method}().alias({c!r})" for c in self.columns)
        return f"{df_var} = {df_var}.with_columns([{exprs}])"

    def to_sql(self, input_table: str, output_table: str) -> str:
        exclude_cols = ", ".join(f'"{c}"' for c in self.columns)
        norm_exprs = []
        for c in self.columns:
            if self.mode == "lower":
                norm_exprs.append(f'LOWER(CAST("{c}" AS VARCHAR)) AS "{c}"')
            elif self.mode == "upper":
                norm_exprs.append(f'UPPER(CAST("{c}" AS VARCHAR)) AS "{c}"')
            else:
                norm_exprs.append(f'CONCAT(UPPER(SUBSTR(CAST("{c}" AS VARCHAR), 1, 1)), LOWER(SUBSTR(CAST("{c}" AS VARCHAR), 2))) AS "{c}"')
        return f'{output_table} AS (SELECT * EXCLUDE ({exclude_cols}), {", ".join(norm_exprs)} FROM {input_table})'
