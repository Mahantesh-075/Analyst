"""Export router for datasets, formula-safe CSV, Parquet, and reproducible scripts."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.errors import AppException
from app.db.models.user import User
from app.export.service import ExportService

router = APIRouter()


@router.get("/datasets/{dataset_id}/export/csv")
async def export_csv(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Download cleaned dataset as a formula-safe CSV file."""
    service = ExportService(db, current_user.id)
    try:
        content, media_type, filename = await service.export_csv(dataset_id)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/datasets/{dataset_id}/export/parquet")
async def export_parquet(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Download cleaned dataset in Apache Parquet format."""
    service = ExportService(db, current_user.id)
    try:
        content, media_type, filename = await service.export_parquet(dataset_id)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/datasets/{dataset_id}/export/python")
async def export_python(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PlainTextResponse:
    """Download reproducible standalone Python transformation script."""
    service = ExportService(db, current_user.id)
    try:
        content, media_type, filename = await service.export_python_script(dataset_id)
        return PlainTextResponse(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/datasets/{dataset_id}/export/sql")
async def export_sql(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PlainTextResponse:
    """Download reproducible DuckDB SQL CTE transformation script."""
    service = ExportService(db, current_user.id)
    try:
        content, media_type, filename = await service.export_sql_script(dataset_id)
        return PlainTextResponse(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
