"""Drop duplicates operation."""

from __future__ import annotations

from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel

from app.ops.base import BaseOp


class DropDuplicatesParams(BaseModel):
    subset: list[str] | None = None
    keep: Literal["first", "last"] = "first"


class DropDuplicatesOp(BaseOp):
    name: ClassVar[str] = "drop_duplicates"

    def __init__(self, subset: list[str] | None = None, keep: Literal["first", "last"] = "first") -> None:
        self.params = DropDuplicatesParams(subset=subset, keep=keep)
        self.subset = self.params.subset
        self.keep = self.params.keep

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        return lf.unique(subset=self.subset, keep=self.keep)

    def to_python(self, df_var: str = "df") -> str:
        subset_repr = repr(self.subset)
        return f"{df_var} = {df_var}.unique(subset={subset_repr}, keep={self.keep!r})"

    def to_sql(self, input_table: str, output_table: str) -> str:
        if not self.subset:
            return f"{output_table} AS (SELECT DISTINCT * FROM {input_table})"
        cols = ", ".join(f'"{c}"' for c in self.subset)
        return f"{output_table} AS (SELECT DISTINCT ON ({cols}) * FROM {input_table})"
