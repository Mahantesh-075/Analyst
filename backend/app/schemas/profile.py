from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ColumnProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    name: str
    inferred_dtype: str
    semantic_type: str | None = None
    semantic_desc: str | None = None
    semantic_confidence: float | None = None
    null_count: int
    null_pct: float
    distinct_count: int | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    missing_tokens: list[str] = Field(default_factory=list)
    pii_types: list[str] = Field(default_factory=list)
    is_pii: bool = False


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_id: UUID
    engine_version: str
    summary: dict[str, Any]
    created_at: datetime
    column_profiles: list[ColumnProfileResponse] = Field(default_factory=list)


class MaskedSampleResponse(BaseModel):
    dataset_id: UUID
    version_id: UUID
    rows: list[dict[str, Any]]
