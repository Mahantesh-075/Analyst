from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PresignedUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    file_size_bytes: int = Field(..., gt=0)
    mime_type: str | None = Field(default=None, max_length=128)


class PresignedUploadResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int
    max_size_bytes: int


class DatasetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_filename: str = Field(..., min_length=1, max_length=255)
    s3_key: str = Field(..., min_length=1)
    description: str | None = Field(default=None, max_length=1000)
    parse_settings: dict[str, Any] = Field(default_factory=dict)


class DatasetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_no: int
    kind: str
    format: str
    size_bytes: int
    sha256: str
    row_count: int | None
    col_count: int | None
    created_at: datetime


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    source_filename: str
    status: str
    current_version_id: UUID | None
    retention_until: datetime | None
    created_at: datetime
    updated_at: datetime
    versions: list[DatasetVersionResponse] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int
    skip: int
    limit: int
