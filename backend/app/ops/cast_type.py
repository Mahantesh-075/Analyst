"""Cast type operation."""

from __future__ import annotations

from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class CastTypeParams(BaseModel):
    column: str = Field(..., min_length=1)
    to: Literal["int", "float", "string", "bool", "date", "datetime", "category"]
    format: str | None = None
    on_error: Literal["null", "fail"] = "fail"


class CastTypeOp(BaseOp):
    name: ClassVar[str] = "cast_type"

    def __init__(
        self,
        column: str,
        to: Literal["int", "float", "string", "bool", "date", "datetime", "category"],
        format: str | None = None,
        on_error: Literal["null", "fail"] = "fail",
    ) -> None:
        self.params = CastTypeParams(column=column, to=to, format=format, on_error=on_error)
        self.column = self.params.column
        self.to = self.params.to
        self.format = self.params.format
        self.on_error = self.params.on_error

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        strict = (self.on_error == "fail")
        col_expr = pl.col(self.column)

        if self.to == "int":
            return lf.with_columns(col_expr.cast(pl.Int64, strict=strict))
        elif self.to == "float":
            return lf.with_columns(col_expr.cast(pl.Float64, strict=strict))
        elif self.to == "string":
            return lf.with_columns(col_expr.cast(pl.String))
        elif self.to == "bool":
            return lf.with_columns(col_expr.cast(pl.Boolean, strict=strict))
        elif self.to == "date":
            if self.format:
                return lf.with_columns(col_expr.cast(pl.String).str.to_date(format=self.format, strict=strict))
            return lf.with_columns(col_expr.cast(pl.Date, strict=strict))
        elif self.to == "datetime":
            if self.format:
                return lf.with_columns(col_expr.cast(pl.String).str.to_datetime(format=self.format, strict=strict))
            return lf.with_columns(col_expr.cast(pl.Datetime, strict=strict))
        elif self.to == "category":
            return lf.with_columns(col_expr.cast(pl.Categorical))
        return lf

    def to_python(self, df_var: str = "df") -> str:
        strict = (self.on_error == "fail")
        c = repr(self.column)
        if self.to == "int":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.Int64, strict={strict}))"
        elif self.to == "float":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.Float64, strict={strict}))"
        elif self.to == "string":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.String))"
        elif self.to == "bool":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.Boolean, strict={strict}))"
        elif self.to == "date":
            if self.format:
                return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.String).str.to_date(format={self.format!r}, strict={strict}))"
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.Date, strict={strict}))"
        elif self.to == "datetime":
            if self.format:
                return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.String).str.to_datetime(format={self.format!r}, strict={strict}))"
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.Datetime, strict={strict}))"
        elif self.to == "category":
            return f"{df_var} = {df_var}.with_columns(pl.col({c}).cast(pl.Categorical))"
        return f"{df_var} = {df_var}"

    def to_sql(self, input_table: str, output_table: str) -> str:
        duck_type = {
            "int": "BIGINT",
            "float": "DOUBLE",
            "string": "VARCHAR",
            "bool": "BOOLEAN",
            "date": "DATE",
            "datetime": "TIMESTAMP",
            "category": "VARCHAR",
        }[self.to]

        cast_fn = "TRY_CAST" if self.on_error == "null" else "CAST"
        if self.to == "date" and self.format:
            expr = f"TRY_STRPTIME(\"{self.column}\", '{self.format}')" if self.on_error == "null" else f"STRPTIME(\"{self.column}\", '{self.format}')"
        elif self.to == "datetime" and self.format:
            expr = f"TRY_STRPTIME(\"{self.column}\", '{self.format}')" if self.on_error == "null" else f"STRPTIME(\"{self.column}\", '{self.format}')"
        else:
            expr = f'{cast_fn}("{self.column}" AS {duck_type})'

        return f'{output_table} AS (SELECT * EXCLUDE ("{self.column}"), {expr} AS "{self.column}" FROM {input_table})'
