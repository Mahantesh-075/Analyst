"""Proposal and transform step repository scoped by dataset owner."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.json_utils import sanitize_for_json
from app.db.models.dataset import Dataset, DatasetVersion
from app.db.models.proposal import CleaningProposal, ValidationResult
from app.db.models.step import TransformStep


class ProposalRepository:
    """Scoped repository managing proposals, transform steps, and validation results."""

    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self.session = session
        self.owner_id = owner_id

    async def _verify_dataset_ownership(self, dataset_id: uuid.UUID) -> Dataset | None:
        stmt = select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.owner_id == self.owner_id,
            Dataset.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_proposals(
        self,
        dataset_id: uuid.UUID,
        base_version_id: uuid.UUID,
        proposals_data: list[dict[str, Any]],
    ) -> list[CleaningProposal]:
        dataset = await self._verify_dataset_ownership(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found or not owned by user.")

        created: list[CleaningProposal] = []
        for i, p in enumerate(proposals_data, 1):
            prop = CleaningProposal(
                dataset_id=dataset_id,
                base_version_id=base_version_id,
                order_index=i,
                op=p["op"],
                params=sanitize_for_json(p["params"]),
                target_columns=p.get("target_columns", []),
                reason=p["reason"],
                impact_preview=sanitize_for_json(p.get("impact_preview", {})),
                severity=p.get("severity", "info"),
                source=p.get("source", "rule"),
                confidence=p.get("confidence", 0.95),
                status="pending",
            )
            self.session.add(prop)
            created.append(prop)

        await self.session.flush()
        return created

    async def list_proposals(self, dataset_id: uuid.UUID) -> Sequence[CleaningProposal]:
        dataset = await self._verify_dataset_ownership(dataset_id)
        if not dataset:
            return []

        stmt = (
            select(CleaningProposal)
            .where(CleaningProposal.dataset_id == dataset_id)
            .order_by(CleaningProposal.order_index.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_proposal(self, dataset_id: uuid.UUID, proposal_id: uuid.UUID) -> CleaningProposal | None:
        dataset = await self._verify_dataset_ownership(dataset_id)
        if not dataset:
            return None

        stmt = select(CleaningProposal).where(
            CleaningProposal.id == proposal_id,
            CleaningProposal.dataset_id == dataset_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        dataset_id: uuid.UUID,
        proposal_id: uuid.UUID,
        status: str,
        edited_params: dict[str, Any] | None = None,
    ) -> CleaningProposal | None:
        prop = await self.get_proposal(dataset_id, proposal_id)
        if not prop:
            return None

        prop.status = status
        prop.decided_at = datetime.now(UTC)
        if edited_params is not None:
            prop.edited_params = sanitize_for_json(edited_params)

        await self.session.flush()
        return prop

    async def bulk_update_status(
        self,
        dataset_id: uuid.UUID,
        proposal_ids: list[uuid.UUID],
        status: str,
    ) -> int:
        dataset = await self._verify_dataset_ownership(dataset_id)
        if not dataset:
            return 0

        stmt = (
            update(CleaningProposal)
            .where(
                CleaningProposal.dataset_id == dataset_id,
                CleaningProposal.id.in_(proposal_ids),
            )
            .values(
                status=status,
                decided_at=datetime.now(UTC),
            )
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return int(getattr(res, "rowcount", 0))

    async def create_cleaned_version(
        self,
        dataset_id: uuid.UUID,
        version_number: int,
        row_count: int,
        col_count: int,
        size_bytes: int,
        sha256: str,
        parent_version_id: uuid.UUID | None = None,
        format: str = "parquet",
    ) -> DatasetVersion:
        version = DatasetVersion(
            dataset_id=dataset_id,
            version_no=version_number,
            kind="cleaned",
            parent_version_id=parent_version_id,
            storage_key=f"datasets/{self.owner_id}/{dataset_id}/v{version_number}_cleaned.parquet",
            format=format,
            size_bytes=size_bytes,
            row_count=row_count,
            col_count=col_count,
            sha256=sha256,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def record_transform_steps(
        self,
        steps: list[dict[str, Any]],
    ) -> list[TransformStep]:
        created: list[TransformStep] = []
        for s in steps:
            step = TransformStep(
                dataset_id=s["dataset_id"],
                from_version_id=s["from_version_id"],
                to_version_id=s["to_version_id"],
                proposal_id=s.get("proposal_id"),
                step_no=s["step_no"],
                op=s["op"],
                params=sanitize_for_json(s["params"]),
                rows_before=s["rows_before"],
                rows_after=s["rows_after"],
                cells_changed=s["cells_changed"],
                engine_version="polars-1.0",
            )
            self.session.add(step)
            created.append(step)

        await self.session.flush()
        return created

    async def record_validation_result(
        self,
        version_id: uuid.UUID,
        passed: bool,
        failures: list[dict[str, Any]],
    ) -> ValidationResult:
        res = ValidationResult(
            version_id=version_id,
            passed=passed,
            failures=failures,
        )
        self.session.add(res)
        await self.session.flush()
        return res

    async def get_transform_steps(self, dataset_id: uuid.UUID) -> Sequence[TransformStep]:
        stmt = (
            select(TransformStep)
            .where(TransformStep.dataset_id == dataset_id)
            .order_by(TransformStep.step_no.asc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()
