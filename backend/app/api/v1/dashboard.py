"""Dashboard and safe query router."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.errors import AppException
from app.dashboard.query_builder import SafeQueryError
from app.db.models.user import User
from app.schemas.dashboard import DashboardResponse, SafeQueryRequest, SafeQueryResult
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("/datasets/{dataset_id}/dashboard", response_model=DashboardResponse)
@router.post("/datasets/{dataset_id}/dashboard/generate", response_model=DashboardResponse)
async def get_or_generate_dashboard(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardResponse:
    """Retrieve or generate deterministic analytics dashboard for a dataset."""
    service = DashboardService(db, current_user.id)
    try:
        return await service.get_dashboard(dataset_id)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dashboard generation failed: {e}",
        ) from e


@router.post("/datasets/{dataset_id}/query", response_model=SafeQueryResult)
async def execute_query(
    dataset_id: uuid.UUID,
    payload: SafeQueryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SafeQueryResult:
    """Execute a safe, allow-listed DuckDB aggregation query against a dataset."""
    service = DashboardService(db, current_user.id)
    try:
        query_dict = payload.model_dump(by_alias=True, exclude_unset=True)
        return await service.execute_custom_query(dataset_id, query_dict)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SafeQueryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution error: {e}",
        ) from e
