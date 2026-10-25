"""Parse date operation."""

from __future__ import annotations

from typing import ClassVar

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class ParseDateParams(BaseModel):
    column: str = Field(..., min_length=1)
    format: str | None = None
    dayfirst: bool = False


class ParseDateOp(BaseOp):
    name: ClassVar[str] = "parse_date"

    def __init__(self, column: str, format: str | None = None, dayfirst: bool = False) -> None:
        self.params = ParseDateParams(column=column, format=format, dayfirst=dayfirst)
        self.column = self.params.column
        self.format = self.params.format
        self.dayfirst = self.params.dayfirst

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        col = pl.col(self.column).cast(pl.String)
        if self.format:
            return lf.with_columns(col.str.to_date(format=self.format, strict=False).alias(self.column))
        elif self.dayfirst:
            # Try day-first parsing
            return lf.with_columns(
                pl.coalesce([
                    col.str.to_date(format="%d/%m/%Y", strict=False),
                    col.str.to_date(format="%d-%m-%Y", strict=False),
                    col.str.to_date(strict=False),
                ]).alias(self.column)
            )
        else:
            return lf.with_columns(col.str.to_date(strict=False).alias(self.column))

    def to_python(self, df_var: str = "df") -> str:
        c = repr(self.column)
        if self.format:
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.String).str.to_date(format={self.format!r}, strict=False).alias({c}))"
        elif self.dayfirst:
            return (
                f"{df_var} = {df_var}.with_columns(pl.coalesce(["
                f"pl.col({c}).cast(pl.String).str.to_date(format='%d/%m/%Y', strict=False), "
                f"pl.col({c}).cast(pl.String).str.to_date(format='%d-%m-%Y', strict=False), "
                f"pl.col({c}).cast(pl.String).str.to_date(strict=False)]).alias({c}))"
            )
        else:
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.String).str.to_date(strict=False).alias({c}))"

    def to_sql(self, input_table: str, output_table: str) -> str:
        if self.format:
            expr = f"TRY_STRPTIME(\"{self.column}\", '{self.format}')"
        else:
            expr = f'TRY_CAST("{self.column}" AS DATE)'
        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}"), {expr} AS "{self.column}" FROM {input_table})'
