"""Pydantic schemas for proposals and transformations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    base_version_id: uuid.UUID
    order_index: int
    op: str
    params: dict[str, Any]
    target_columns: list[str]
    reason: str
    impact_preview: dict[str, Any]
    severity: str
    source: str
    confidence: float | None
    status: str
    edited_params: dict[str, Any] | None
    decided_at: datetime | None
    created_at: datetime


class UpdateProposalStatusRequest(BaseModel):
    status: Literal["pending", "accepted", "rejected"]
    edited_params: dict[str, Any] | None = None


class BulkUpdateProposalsRequest(BaseModel):
    proposal_ids: list[uuid.UUID]
    status: Literal["accepted", "rejected"]


class ApplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    kind: str
    row_count: int
    col_count: int
    size_bytes: int
    sha256: str
    status: str
