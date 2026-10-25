from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.profile import MaskedSampleResponse, ProfileResponse
from app.services.profiling import ProfilingService

router = APIRouter(prefix="/datasets", tags=["profiling"])


@router.get(
    "/{dataset_id}/profile",
    response_model=ProfileResponse,
    summary="Get deterministic profile of dataset",
)
async def get_dataset_profile(
    dataset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    service = ProfilingService(session, current_user.id)
    profile = await service.get_profile(dataset_id)
    return ProfileResponse.model_validate(profile)


@router.post(
    "/{dataset_id}/profile",
    response_model=ProfileResponse,
    summary="Re-compute deterministic profile",
)
async def compute_dataset_profile(
    dataset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    service = ProfilingService(session, current_user.id)
    profile = await service.profile_dataset(dataset_id)
    await session.commit()
    return ProfileResponse.model_validate(profile)


@router.get(
    "/{dataset_id}/sample",
    response_model=MaskedSampleResponse,
    summary="Get 20-row PII-masked sample",
)
async def get_dataset_sample(
    dataset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaskedSampleResponse:
    service = ProfilingService(session, current_user.id)
    profile = await service.get_profile(dataset_id)
    rows = await service.get_masked_sample(dataset_id)
    return MaskedSampleResponse(
        dataset_id=dataset_id,
        version_id=profile.version_id,
        rows=rows,
    )
