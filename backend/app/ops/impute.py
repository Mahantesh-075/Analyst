"""Impute nulls operation."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class ImputeParams(BaseModel):
    column: str = Field(..., min_length=1)
    strategy: Literal["mean", "median", "mode", "constant", "forward_fill"]
    value: Any = None


class ImputeOp(BaseOp):
    name: ClassVar[str] = "impute"

    def __init__(
        self,
        column: str,
        strategy: Literal["mean", "median", "mode", "constant", "forward_fill"],
        value: Any = None,
    ) -> None:
        self.params = ImputeParams(column=column, strategy=strategy, value=value)
        self.column = self.params.column
        self.strategy = self.params.strategy
        self.value = self.params.value

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        col = pl.col(self.column)
        if self.strategy == "constant":
            return lf.with_columns(col.fill_null(self.value).alias(self.column))
        elif self.strategy == "mean":
            return lf.with_columns(col.fill_null(col.mean()).alias(self.column))
        elif self.strategy == "median":
            return lf.with_columns(col.fill_null(col.median()).alias(self.column))
        elif self.strategy == "mode":
            return lf.with_columns(col.fill_null(col.mode().first()).alias(self.column))
        elif self.strategy == "forward_fill":
            return lf.with_columns(col.forward_fill().alias(self.column))
        return lf

    def to_python(self, df_var: str = "df") -> str:
        c = repr(self.column)
        if self.strategy == "constant":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).fill_null({self.value!r}).alias({c}))"
        elif self.strategy == "mean":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).fill_null(pl.col({c}).mean()).alias({c}))"
        elif self.strategy == "median":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).fill_null(pl.col({c}).median()).alias({c}))"
        elif self.strategy == "mode":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).fill_null(pl.col({c}).mode().first()).alias({c}))"
        elif self.strategy == "forward_fill":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).forward_fill().alias({c}))"
        return f"{df_var} = {df_var}"

    def to_sql(self, input_table: str, output_table: str) -> str:
        if self.strategy == "constant":
            val_sql = f"'{self.value}'" if isinstance(self.value, str) else str(self.value)
            expr = f'COALESCE("{self.column}", {val_sql})'
        elif self.strategy == "mean":
            expr = f'COALESCE("{self.column}", AVG("{self.column}") OVER ())'
        elif self.strategy == "median":
            expr = f'COALESCE("{self.column}", MEDIAN("{self.column}") OVER ())'
        elif self.strategy == "mode":
            expr = f'COALESCE("{self.column}", MODE("{self.column}") OVER ())'
        elif self.strategy == "forward_fill":
            expr = f'COALESCE("{self.column}", LAG("{self.column}") IGNORE NULLS OVER ())'
        else:
            expr = f'"{self.column}"'
        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}"), {expr} AS "{self.column}" FROM {input_table})'
