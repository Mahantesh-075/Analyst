import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models.user import User
from app.db.repositories.job import JobRepository
from app.schemas.job import JobResponse
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job details and status",
)
async def get_job(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> JobResponse:
    repo = JobRepository(session, current_user.id)
    job = await repo.get_job(job_id)
    return JobResponse.model_validate(job)


@router.get(
    "/{job_id}/events",
    summary="SSE stream for job progress events",
)
async def stream_job_events(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    # Security: Verify user owns the job before opening event stream (404 on invalid)
    repo = JobRepository(session, current_user.id)
    job = await repo.get_job(job_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        channel = f"job:{job_id}:events"
        await pubsub.subscribe(channel)

        # Yield current initial state
        initial_msg = json.dumps({
            "job_id": str(job.id),
            "progress": job.progress,
            "status": job.status,
            "message": "Connected to job event stream",
        })
        yield f"data: {initial_msg}\n\n"

        if job.status in ["succeeded", "failed", "cancelled"]:
            await pubsub.unsubscribe(channel)
            await r.close()
            return

        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("data"):
                    raw_data = msg["data"]
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")
                    yield f"data: {raw_data}\n\n"

                    # Check for completion to close stream cleanly
                    try:
                        parsed = json.loads(raw_data)
                        if parsed.get("status") in ["succeeded", "failed", "cancelled"]:
                            break
                    except Exception:
                        pass
                await asyncio.sleep(0.2)
        finally:
            await pubsub.unsubscribe(channel)
            await r.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/datasets/{dataset_id}/ingest",
    response_model=JobResponse,
    summary="Trigger dataset ingestion and normalization",
)
async def trigger_ingestion(
    dataset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> JobResponse:
    repo = JobRepository(session, current_user.id)
    job = await repo.create_job(
        job_type="ingest",
        dataset_id=dataset_id,
        payload={"dataset_id": str(dataset_id)},
    )
    await session.commit()

    # Run ingestion synchronously or dispatch
    # Using IngestionService to complete ingestion and emit progress
    ingest_svc = IngestionService(session, current_user.id)
    try:
        await repo.update_status(job.id, "running", progress=10)
        await session.commit()

        await ingest_svc.ingest_dataset(dataset_id=dataset_id, job_id=job.id)
        job = await repo.update_status(job.id, "succeeded", progress=100)
        await session.commit()
    except Exception as e:
        await repo.update_status(
            job.id,
            "failed",
            error={"message": str(e)},
        )
        await session.commit()
        raise

    return JobResponse.model_validate(job)
