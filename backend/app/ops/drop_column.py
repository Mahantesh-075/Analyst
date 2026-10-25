"""Drop column operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class DropColumnParams(BaseModel):
    column: str = Field(..., min_length=1)


class DropColumnOp(BaseOp):
    name: ClassVar[str] = "drop_column"

    def __init__(self, column: str) -> None:
        self.params = DropColumnParams(column=column)
        self.column = self.params.column

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.drop(self.column)

    def to_python(self, df_var: str = "df") -> str:
        return f"{df_var} = {df_var}.drop({self.column!r})"

    def to_sql(self, input_table: str, output_table: str) -> str:
        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}") FROM {input_table})'
