"""Pydantic schemas for safe queries, dashboard specifications, and visual charts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DimensionSpec(BaseModel):
    field: str
    bucket: str | None = None


class MeasureSpec(BaseModel):
    field: str | None = None
    agg: str
    as_: str | None = Field(default=None, alias="as")


class FilterSpec(BaseModel):
    field: str
    op: str
    value: Any = None


class OrderBySpec(BaseModel):
    field: str
    dir: str = "desc"


class SafeQueryRequest(BaseModel):
    dimensions: list[DimensionSpec] = Field(default_factory=list)
    measures: list[MeasureSpec] = Field(default_factory=list)
    filters: list[FilterSpec] = Field(default_factory=list)
    order_by: list[OrderBySpec] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=1000)


class SafeQueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class DashboardResponse(BaseModel):
    dataset_id: str
    version_id: str
    spec: dict[str, Any]
    kpis: list[dict[str, Any]]
    charts: list[dict[str, Any]]
    narratives_rendered: list[str]
