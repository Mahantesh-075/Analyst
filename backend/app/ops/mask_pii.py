"""Mask PII operation."""

from __future__ import annotations

from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class MaskPiiParams(BaseModel):
    column: str = Field(..., min_length=1)
    method: Literal["hash", "redact", "partial"]


class MaskPiiOp(BaseOp):
    name: ClassVar[str] = "mask_pii"

    def __init__(self, column: str, method: Literal["hash", "redact", "partial"]) -> None:
        self.params = MaskPiiParams(column=column, method=method)
        self.column = self.params.column
        self.method = self.params.method

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        col = pl.col(self.column).cast(pl.String)
        if self.method == "redact":
            expr = (
                pl.when(col.is_not_null())
                .then(pl.lit("***REDACTED***"))
                .otherwise(None)
                .alias(self.column)
            )
        elif self.method == "hash":
            # UInt64 hash converted to string
            expr = (
                pl.when(col.is_not_null())
                .then(col.hash().cast(pl.String))
                .otherwise(None)
                .alias(self.column)
            )
        else:  # partial
            expr = (
                pl.when(col.is_null())
                .then(None)
                .when(col.str.len_chars() > 4)
                .then(
                    col.str.slice(0, 2)
                    + pl.lit("****")
                    + col.str.slice(-2, 2)
                )
                .otherwise(pl.lit("****"))
                .alias(self.column)
            )
        return lf.with_columns(expr)

    def to_python(self, df_var: str = "df") -> str:
        c = repr(self.column)
        if self.method == "redact":
            return f"{df_var} = {df_var}.with_columns(pl.when(pl.col({c}).is_not_null()).then(pl.lit('***REDACTED***')).otherwise(None).alias({c}))"
        elif self.method == "hash":
            return f"{df_var} = {df_var}.with_columns(pl.when(pl.col({c}).is_not_null()).then(pl.col({c}).cast(pl.String).hash().cast(pl.String)).otherwise(None).alias({c}))"
        else:
            return (
                f"_col = pl.col({c}).cast(pl.String)\n"
                f"{df_var} = {df_var}.with_columns("
                f"pl.when(_col.is_null()).then(None)"
                f".when(_col.str.len_chars() > 4).then(_col.str.slice(0, 2) + pl.lit('****') + _col.str.slice(-2, 2))"
                f".otherwise(pl.lit('****')).alias({c}))"
            )

    def to_sql(self, input_table: str, output_table: str) -> str:
        c = self.column
        if self.method == "redact":
            expr = f"CASE WHEN \"{c}\" IS NOT NULL THEN '***REDACTED***' ELSE NULL END"
        elif self.method == "hash":
            expr = f"CASE WHEN \"{c}\" IS NOT NULL THEN SHA256(CAST(\"{c}\" AS VARCHAR)) ELSE NULL END"
        else:
            expr = (
                f"CASE WHEN \"{c}\" IS NULL THEN NULL "
                f"WHEN LENGTH(CAST(\"{c}\" AS VARCHAR)) > 4 THEN SUBSTR(CAST(\"{c}\" AS VARCHAR), 1, 2) || '****' || SUBSTR(CAST(\"{c}\" AS VARCHAR), LENGTH(CAST(\"{c}\" AS VARCHAR)) - 1, 2) "
                f"ELSE '****' END"
            )
        return f'{output_table} AS (SELECT * EXCLUDE ("{c}"), {expr} AS "{c}" FROM {input_table})'
