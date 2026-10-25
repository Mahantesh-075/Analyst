from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.db.models.job import Job
from app.db.repositories.base import ScopedRepository


class JobRepository(ScopedRepository[Job]):
    def __init__(self, session: AsyncSession, owner_id: UUID) -> None:
        super().__init__(Job, session, owner_id)

    async def create_job(
        self,
        job_type: str,
        dataset_id: UUID | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Job:
        job = Job(
            owner_id=self.owner_id,
            dataset_id=dataset_id,
            type=job_type,
            status="queued",
            progress=0,
            idempotency_key=idempotency_key,
            payload=payload or {},
            attempts=0,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: UUID) -> Job:
        query = select(Job).where(Job.owner_id == self.owner_id, Job.id == job_id)
        result = await self.session.execute(query)
        job = result.scalar_one_or_none()
        if not job:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Job not found: {job_id}",
                status_code=404,
            )
        return job

    async def update_status(
        self,
        job_id: UUID,
        status: str,
        progress: int | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> Job:
        job = await self.get_job(job_id)
        job.status = status
        if progress is not None:
            job.progress = progress
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        if status == "running" and not job.started_at:
            job.started_at = datetime.now(UTC)
        elif status in ["succeeded", "failed", "cancelled"]:
            job.finished_at = datetime.now(UTC)
        await self.session.flush()
        return job
