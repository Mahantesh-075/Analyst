"""Split column operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class SplitColumnParams(BaseModel):
    column: str = Field(..., min_length=1)
    delimiter: str = Field(..., min_length=1, max_length=8)
    into: list[str] = Field(..., min_length=2, max_length=10)


class SplitColumnOp(BaseOp):
    name: ClassVar[str] = "split_column"

    def __init__(self, column: str, delimiter: str, into: list[str]) -> None:
        self.params = SplitColumnParams(column=column, delimiter=delimiter, into=into)
        self.column = self.params.column
        self.delimiter = self.params.delimiter
        self.into = self.params.into

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        split_expr = pl.col(self.column).cast(pl.String).str.split(self.delimiter)
        new_cols = [split_expr.list.get(i).alias(name) for i, name in enumerate(self.into)]
        return lf.with_columns(new_cols).drop(self.column)

    def to_python(self, df_var: str = "df") -> str:
        c = repr(self.column)
        d = repr(self.delimiter)
        col_exprs = ", ".join(f"_split.list.get({i}).alias({name!r})" for i, name in enumerate(self.into))
        return (
            f"_split = pl.col({c}).cast(pl.String).str.split({d})\n"
            f"{df_var} = {df_var}.with_columns([{col_exprs}]).drop({c})"
        )

    def to_sql(self, input_table: str, output_table: str) -> str:
        d_esc = self.delimiter.replace("'", "''")
        new_col_sql = ", ".join(
            f"STRING_SPLIT(CAST(\"{self.column}\" AS VARCHAR), '{d_esc}')[{i+1}] AS \"{name}\""
            for i, name in enumerate(self.into)
        )
        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}"), {new_col_sql} FROM {input_table})'
