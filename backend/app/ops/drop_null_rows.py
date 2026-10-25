"""Drop null rows operation."""

from __future__ import annotations

from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class DropNullRowsParams(BaseModel):
    columns: list[str] = Field(..., min_length=1)
    how: Literal["any", "all"] = "any"


class DropNullRowsOp(BaseOp):
    name: ClassVar[str] = "drop_null_rows"

    def __init__(self, columns: list[str], how: Literal["any", "all"] = "any") -> None:
        self.params = DropNullRowsParams(columns=columns, how=how)
        self.columns = self.params.columns
        self.how = self.params.how

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        if self.how == "any":
            return lf.drop_nulls(subset=self.columns)
        else:
            return lf.filter(~pl.all_horizontal([pl.col(c).is_null() for c in self.columns]))

    def to_python(self, df_var: str = "df") -> str:
        cols_repr = repr(self.columns)
        if self.how == "any":
            return f"{df_var} = {df_var}.drop_nulls(subset={cols_repr})"
        else:
            exprs = ", ".join(f"pl.col({c!r}).is_null()" for c in self.columns)
            return f"{df_var} = {df_var}.filter(~pl.all_horizontal([{exprs}]))"

    def to_sql(self, input_table: str, output_table: str) -> str:
        if self.how == "any":
            where_clause = " AND ".join(f'"{c}" IS NOT NULL' for c in self.columns)
        else:
            null_checks = " AND ".join(f'"{c}" IS NULL' for c in self.columns)
            where_clause = f"NOT ({null_checks})"
        return f"{output_table} AS (SELECT * FROM {input_table} WHERE {where_clause})"
