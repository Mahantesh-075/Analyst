"""Handle outliers operation."""

from __future__ import annotations

from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel, Field

from app.ops.base import BaseOp


class HandleOutliersParams(BaseModel):
    column: str = Field(..., min_length=1)
    method: Literal["iqr", "zscore"]
    threshold: float = Field(1.5, gt=0)
    action: Literal["flag", "clip", "null"]


class HandleOutliersOp(BaseOp):
    name: ClassVar[str] = "handle_outliers"

    def __init__(
        self,
        column: str,
        method: Literal["iqr", "zscore"],
        action: Literal["flag", "clip", "null"],
        threshold: float = 1.5,
    ) -> None:
        self.params = HandleOutliersParams(column=column, method=method, threshold=threshold, action=action)
        self.column = self.params.column
        self.method = self.params.method
        self.threshold = self.params.threshold
        self.action = self.params.action

    def _bounds_expr(self) -> tuple[pl.Expr, pl.Expr]:
        col = pl.col(self.column)
        if self.method == "iqr":
            q1 = col.quantile(0.25)
            q3 = col.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - pl.lit(self.threshold) * iqr
            upper = q3 + pl.lit(self.threshold) * iqr
        else:
            mean = col.mean()
            std = col.std()
            lower = mean - pl.lit(self.threshold) * std
            upper = mean + pl.lit(self.threshold) * std
        return lower, upper

    def apply(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        lower, upper = self._bounds_expr()
        col = pl.col(self.column)

        if self.action == "flag":
            flag_expr = ((col < lower) | (col > upper)).alias(f"{self.column}_is_outlier")
            return lf.with_columns(flag_expr)
        elif self.action == "clip":
            clip_expr = col.clip(lower, upper).alias(self.column)
            return lf.with_columns(clip_expr)
        else:  # null
            null_expr = (
                pl.when((col < lower) | (col > upper))
                .then(None)
                .otherwise(col)
                .alias(self.column)
            )
            return lf.with_columns(null_expr)

    def to_python(self, df_var: str = "df") -> str:
        c = repr(self.column)
        t = repr(self.threshold)
        if self.method == "iqr":
            bounds = (
                f"_q1 = pl.col({c}).quantile(0.25)\n"
                f"_q3 = pl.col({c}).quantile(0.75)\n"
                f"_iqr = _q3 - _q1\n"
                f"_lower = _q1 - pl.lit({t}) * _iqr\n"
                f"_upper = _q3 + pl.lit({t}) * _iqr"
            )
        else:
            bounds = (
                f"_mean = pl.col({c}).mean()\n"
                f"_std = pl.col({c}).std()\n"
                f"_lower = _mean - pl.lit({t}) * _std\n"
                f"_upper = _mean + pl.lit({t}) * _std"
            )

        if self.action == "flag":
            action_code = f"{df_var} = {df_var}.with_columns(((pl.col({c}) < _lower) | (pl.col({c}) > _upper)).alias(f'{{{c}}}_is_outlier'))"
        elif self.action == "clip":
            action_code = f"{df_var} = {df_var}.with_columns(pl.col({c}).clip(_lower, _upper).alias({c}))"
        else:
            action_code = f"{df_var} = {df_var}.with_columns(pl.when((pl.col({c}) < _lower) | (pl.col({c}) > _upper)).then(None).otherwise(pl.col({c})).alias({c}))"

        return f"{bounds}\n{action_code}"

    def to_sql(self, input_table: str, output_table: str) -> str:
        t = self.threshold
        c = self.column
        if self.method == "iqr":
            stats_cte = (
                f'_stats_{output_table} AS (\n'
                f'    SELECT \n'
                f'        quantile_cont("{c}", 0.25) AS _q1,\n'
                f'        quantile_cont("{c}", 0.75) AS _q3,\n'
                f'        (quantile_cont("{c}", 0.75) - quantile_cont("{c}", 0.25)) AS _iqr\n'
                f'    FROM {input_table}\n'
                f')'
            )
            lower_expr = f'(_s._q1 - {t} * _s._iqr)'
            upper_expr = f'(_s._q3 + {t} * _s._iqr)'
        else:
            stats_cte = (
                f'_stats_{output_table} AS (\n'
                f'    SELECT AVG("{c}") AS _mean, STDDEV("{c}") AS _std FROM {input_table}\n'
                f')'
            )
            lower_expr = f'(_s._mean - {t} * _s._std)'
            upper_expr = f'(_s._mean + {t} * _s._std)'

        if self.action == "flag":
            main_query = (
                f'{output_table} AS (\n'
                f'    SELECT {input_table}.*, ("{c}" < {lower_expr} OR "{c}" > {upper_expr}) AS "{c}_is_outlier"\n'
                f'    FROM {input_table} CROSS JOIN _stats_{output_table} AS _s\n'
                f')'
            )
        elif self.action == "clip":
            main_query = (
                f'{output_table} AS (\n'
                f'    SELECT * EXCLUDE ("{c}"), CASE WHEN "{c}" < {lower_expr} THEN {lower_expr} WHEN "{c}" > {upper_expr} THEN {upper_expr} ELSE "{c}" END AS "{c}"\n'
                f'    FROM {input_table} CROSS JOIN _stats_{output_table} AS _s\n'
                f')'
            )
        else:
            main_query = (
                f'{output_table} AS (\n'
                f'    SELECT * EXCLUDE ("{c}"), CASE WHEN "{c}" < {lower_expr} OR "{c}" > {upper_expr} THEN NULL ELSE "{c}" END AS "{c}"\n'
                f'    FROM {input_table} CROSS JOIN _stats_{output_table} AS _s\n'
                f')'
            )

        return f"{stats_cte},\n{main_query}"
