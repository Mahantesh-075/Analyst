"""Proposal and transformation apply endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.proposal import (
    ApplyResponse,
    BulkUpdateProposalsRequest,
    ProposalResponse,
    UpdateProposalStatusRequest,
)
from app.services.apply import ApplyService
from app.services.proposal import ProposalService

router = APIRouter(tags=["proposals"])


@router.post("/datasets/{dataset_id}/proposals/generate", response_model=list[ProposalResponse])
async def generate_proposals(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Sequence[ProposalResponse]:
    """Deterministically analyze dataset profile and generate cleaning proposals."""
    service = ProposalService(db, current_user.id)
    try:
        proposals = await service.generate_proposals(dataset_id)
        return [ProposalResponse.model_validate(p) for p in proposals]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/datasets/{dataset_id}/proposals", response_model=list[ProposalResponse])
async def list_proposals(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Sequence[ProposalResponse]:
    """List all proposals for a dataset."""
    service = ProposalService(db, current_user.id)
    try:
        proposals = await service.list_proposals(dataset_id)
        return [ProposalResponse.model_validate(p) for p in proposals]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/datasets/{dataset_id}/proposals/{proposal_id}", response_model=ProposalResponse)
async def update_proposal(
    dataset_id: uuid.UUID,
    proposal_id: uuid.UUID,
    payload: UpdateProposalStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProposalResponse:
    """Accept or reject an individual proposal with optional parameter edits."""
    service = ProposalService(db, current_user.id)
    try:
        updated = await service.update_proposal_status(
            dataset_id=dataset_id,
            proposal_id=proposal_id,
            status=payload.status,
            edited_params=payload.edited_params,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        return ProposalResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/datasets/{dataset_id}/proposals/bulk")
async def bulk_update_proposals(
    dataset_id: uuid.UUID,
    payload: BulkUpdateProposalsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, int]:
    """Bulk accept or reject proposals."""
    service = ProposalService(db, current_user.id)
    try:
        updated_count = await service.bulk_update_status(
            dataset_id=dataset_id,
            proposal_ids=payload.proposal_ids,
            status=payload.status,
        )
        return {"updated": updated_count}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/datasets/{dataset_id}/apply", response_model=ApplyResponse)
async def apply_proposals(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApplyResponse:
    """Execute all accepted proposals, creating an immutable cleaned dataset version."""
    service = ApplyService(db, current_user.id)
    try:
        cleaned_version = await service.apply_proposals(dataset_id)
        return ApplyResponse(
            dataset_id=dataset_id,
            version_id=cleaned_version.id,
            version_number=cleaned_version.version_no,
            kind=cleaned_version.kind,
            row_count=cleaned_version.row_count or 0,
            col_count=cleaned_version.col_count or 0,
            size_bytes=cleaned_version.size_bytes or 0,
            sha256=cleaned_version.sha256 or "",
            status="cleaned",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
