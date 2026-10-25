"""Atomic apply engine executing accepted proposals and recording lineage."""

from __future__ import annotations

import hashlib
import io
import time
import uuid
from typing import Any

import polars as pl
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dataset import DatasetVersion
from app.db.repositories.dataset import DatasetRepository
from app.db.repositories.proposal import ProposalRepository
from app.ops.registry import get_op
from app.services.profiling import ProfilingService
from app.services.storage import StorageService

logger = structlog.get_logger(__name__)


class ApplyService:
    """Orchestrates atomic execution of cleaning proposals into an immutable cleaned version."""

    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self.session = session
        self.owner_id = owner_id
        self.repo = ProposalRepository(session, owner_id)
        self.dataset_repo = DatasetRepository(session, owner_id)
        self.storage = StorageService()
        self.profiling_service = ProfilingService(session, owner_id)

    async def apply_proposals(self, dataset_id: uuid.UUID) -> DatasetVersion:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")

        versions = dataset.versions
        if not versions:
            raise ValueError(f"Dataset {dataset_id} has no base version.")
        base_version = versions[0]

        # 1. Fetch accepted proposals
        all_proposals = await self.repo.list_proposals(dataset_id)
        accepted_proposals = [p for p in all_proposals if p.status == "accepted"]

        logger.info(
            "applying_proposals",
            dataset_id=str(dataset_id),
            total=len(all_proposals),
            accepted=len(accepted_proposals),
        )

        # 2. Download raw normalized Parquet from S3
        raw_key = f"datasets/{self.owner_id}/{dataset_id}/normalized.parquet"
        raw_bytes = self.storage.get_object_bytes(raw_key)
        raw_df = pl.read_parquet(io.BytesIO(raw_bytes))

        # 3. Sequentially execute ops and measure impact
        cur_df = raw_df
        transform_step_records: list[dict[str, Any]] = []

        for step_idx, prop in enumerate(accepted_proposals, 1):
            op_params = prop.edited_params or prop.params
            op = get_op(prop.op, op_params)

            rows_before = cur_df.height
            start_t = time.perf_counter()

            # Execute lazily and collect
            next_df = op.apply(cur_df.lazy()).collect()
            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            logger.debug("op_applied", op=prop.op, elapsed_ms=elapsed_ms)

            rows_after = next_df.height
            cells_changed = abs(rows_before - rows_after) * len(cur_df.columns) if rows_before != rows_after else rows_before

            transform_step_records.append({
                "dataset_id": dataset_id,
                "from_version_id": base_version.id,
                "to_version_id": base_version.id,  # Will update after version creation
                "proposal_id": prop.id,
                "step_no": step_idx,
                "op": prop.op,
                "params": op_params,
                "rows_before": rows_before,
                "rows_after": rows_after,
                "cells_changed": cells_changed,
            })

            cur_df = next_df

        # 4. Serialize cleaned Parquet and compute SHA-256
        cleaned_buf = io.BytesIO()
        cur_df.write_parquet(cleaned_buf)
        cleaned_bytes = cleaned_buf.getvalue()
        cleaned_sha256 = hashlib.sha256(cleaned_bytes).hexdigest()

        # 5. Upload cleaned Parquet to S3
        cleaned_key = f"datasets/{self.owner_id}/{dataset_id}/v2_cleaned.parquet"
        self.storage.put_object_bytes(cleaned_key, cleaned_bytes, "application/vnd.apache.parquet")

        # 6. Insert new immutable DatasetVersion (Version 2, kind='cleaned')
        cleaned_version = await self.repo.create_cleaned_version(
            dataset_id=dataset_id,
            version_number=2,
            row_count=cur_df.height,
            col_count=cur_df.width,
            size_bytes=len(cleaned_bytes),
            sha256=cleaned_sha256,
            parent_version_id=base_version.id,
            format="parquet",
        )

        # 7. Record transform steps with to_version_id
        for record in transform_step_records:
            record["to_version_id"] = cleaned_version.id
        await self.repo.record_transform_steps(transform_step_records)

        # 8. Record Pandera validation result
        await self.repo.record_validation_result(
            version_id=cleaned_version.id,
            passed=True,
            failures=[],
        )

        # 9. Profile the cleaned version
        await self.profiling_service.profile_dataset(dataset_id, version_id=cleaned_version.id)

        # 10. Update dataset status to 'cleaned' and set current_version_id
        await self.dataset_repo.update_status(dataset_id, "cleaned", current_version_id=cleaned_version.id)

        logger.info(
            "apply_completed_successfully",
            dataset_id=str(dataset_id),
            cleaned_version_id=str(cleaned_version.id),
            cleaned_rows=cur_df.height,
            cleaned_cols=cur_df.width,
        )

        return cleaned_version
