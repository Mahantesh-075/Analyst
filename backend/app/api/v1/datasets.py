from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.dataset import (
    DatasetCreateRequest,
    DatasetListResponse,
    DatasetResponse,
    DatasetUpdateRequest,
    PresignedUploadRequest,
    PresignedUploadResponse,
)
from app.services.dataset import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post(
    "/upload-url",
    response_model=PresignedUploadResponse,
    summary="Generate presigned S3 upload URL",
)
async def generate_upload_url(
    data: PresignedUploadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PresignedUploadResponse:
    service = DatasetService(session, current_user.id)
    res = await service.generate_upload_url(
        filename=data.filename,
        file_size_bytes=data.file_size_bytes,
        mime_type=data.mime_type,
    )
    return PresignedUploadResponse(**res)


@router.post(
    "",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register newly uploaded dataset",
)
async def create_dataset(
    data: DatasetCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DatasetResponse:
    service = DatasetService(session, current_user.id)
    dataset = await service.create_dataset(
        name=data.name,
        source_filename=data.source_filename,
        s3_key=data.s3_key,
        description=data.description,
        parse_settings=data.parse_settings,
    )
    return DatasetResponse.model_validate(dataset)


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List current user's datasets",
)
async def list_datasets(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(default=None, description="Search dataset name or description"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> DatasetListResponse:
    service = DatasetService(session, current_user.id)
    items, total = await service.list_datasets(
        search=search,
        skip=skip,
        limit=limit,
    )
    return DatasetListResponse(
        items=[DatasetResponse.model_validate(d) for d in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Get single dataset by ID",
)
async def get_dataset(
    dataset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DatasetResponse:
    service = DatasetService(session, current_user.id)
    dataset = await service.get_dataset(dataset_id=dataset_id)
    return DatasetResponse.model_validate(dataset)


@router.patch(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Update dataset metadata",
)
async def update_dataset(
    dataset_id: UUID,
    data: DatasetUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DatasetResponse:
    service = DatasetService(session, current_user.id)
    dataset = await service.update_dataset(
        dataset_id=dataset_id,
        name=data.name,
        description=data.description,
    )
    return DatasetResponse.model_validate(dataset)


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete dataset (retained 30 days)",
)
async def delete_dataset(
    dataset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = DatasetService(session, current_user.id)
    await service.delete_dataset(dataset_id=dataset_id)
