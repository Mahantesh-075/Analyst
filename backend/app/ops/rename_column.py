"""Rename column operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class RenameColumnParams(BaseModel):
    column: str = Field(..., min_length=1)
    new_name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_ ]{0,62}$")


class RenameColumnOp(BaseOp):
    name: ClassVar[str] = "rename_column"

    def __init__(self, column: str, new_name: str) -> None:
        self.params = RenameColumnParams(column=column, new_name=new_name)
        self.column = self.params.column
        self.new_name = self.params.new_name

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.rename({self.column: self.new_name})

    def to_python(self, df_var: str = "df") -> str:
        return f"{df_var} = {df_var}.rename({{ {self.column!r}: {self.new_name!r} }})"

    def to_sql(self, input_table: str, output_table: str) -> str:
        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}"), "{self.column}" AS "{self.new_name}" FROM {input_table})'
