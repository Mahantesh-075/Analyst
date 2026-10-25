"""Map values operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class MapValuesParams(BaseModel):
    column: str = Field(..., min_length=1)
    mapping: dict[str, str] = Field(..., min_length=1)


class MapValuesOp(BaseOp):
    name: ClassVar[str] = "map_values"

    def __init__(self, column: str, mapping: dict[str, str]) -> None:
        self.params = MapValuesParams(column=column, mapping=mapping)
        self.column = self.params.column
        self.mapping = self.params.mapping

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.with_columns(
            pl.col(self.column).replace_strict(self.mapping, default=pl.col(self.column)).alias(self.column)
        )

    def to_python(self, df_var: str = "df") -> str:
        c = repr(self.column)
        m = repr(self.mapping)
        return f"{df_var} = {df_var}.with_columns(pl.col({c}).replace_strict({m}, default=pl.col({c})).alias({c}))"

    def to_sql(self, input_table: str, output_table: str) -> str:
        cases = []
        for k, v in self.mapping.items():
            k_esc = k.replace("'", "''")
            v_esc = v.replace("'", "''")
            cases.append(f"WHEN '{k_esc}' THEN '{v_esc}'")
        case_stmt = f"CASE CAST(\"{self.column}\" AS VARCHAR) " + " ".join(cases) + f" ELSE CAST(\"{self.column}\" AS VARCHAR) END"
        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}"), {case_stmt} AS "{self.column}" FROM {input_table})'
