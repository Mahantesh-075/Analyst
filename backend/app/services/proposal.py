"""Proposal service orchestrating deterministic rule engine and LLM suggestions."""

from __future__ import annotations

import io
import uuid
from collections.abc import Sequence
from typing import Any

import polars as pl
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.proposal import CleaningProposal
from app.db.repositories.dataset import DatasetRepository
from app.db.repositories.profile import ProfileRepository
from app.db.repositories.proposal import ProposalRepository
from app.llm.client import LLMClient
from app.proposals.rules import generate_rule_proposals
from app.services.storage import StorageService

logger = structlog.get_logger(__name__)


class ProposalService:
    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self.session = session
        self.owner_id = owner_id
        self.repo = ProposalRepository(session, owner_id)
        self.dataset_repo = DatasetRepository(session, owner_id)
        self.profile_repo = ProfileRepository(session)
        self.storage = StorageService()
        self.llm = LLMClient()

    async def generate_proposals(self, dataset_id: uuid.UUID) -> Sequence[CleaningProposal]:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")

        if not dataset.versions:
            raise ValueError(f"Dataset {dataset_id} has no registered versions.")

        base_version = dataset.versions[0]
        ds_profile = await self.profile_repo.get_by_version_id(base_version.id)
        if not ds_profile:
            raise ValueError(f"Dataset {dataset_id} has not been profiled yet.")

        col_profiles = ds_profile.column_profiles

        # Load sample for impact preview
        sample_df: pl.DataFrame | None = None
        norm_key = f"datasets/{self.owner_id}/{dataset_id}/normalized.parquet"
        if self.storage.object_exists(norm_key):
            parquet_bytes = self.storage.get_object_bytes(norm_key)
            sample_df = pl.read_parquet(io.BytesIO(parquet_bytes)).head(20)

        # 1. Deterministic Rule Proposals
        rule_props = generate_rule_proposals(ds_profile, list(col_profiles), sample_df)

        # 2. LLM Proposals (if enabled, zero PII sample)
        llm_props: list[dict[str, Any]] = []
        if self.llm.enabled:
            col_meta = [
                {
                    "column": c.name,
                    "inferred_type": c.inferred_dtype,
                    "null_pct": c.null_pct,
                    "distinct_count": c.distinct_count,
                    "is_pii": c.is_pii,
                    "pii_types": list(c.pii_types),
                }
                for c in col_profiles
            ]
            masked_sample = sample_df.to_dicts() if sample_df is not None else []
            llm_props = await self.llm.generate_proposals(col_meta, masked_sample)

        # Merge proposals, avoiding duplicate op+params
        combined_props = list(rule_props)
        existing_signatures = {(p["op"], str(sorted(p["params"].items()))) for p in rule_props}

        for lp in llm_props:
            step = lp.get("step", {})
            op_name = step.get("op")
            params = step.get("params", {})
            sig = (op_name, str(sorted(params.items())))
            if sig not in existing_signatures:
                combined_props.append({
                    "op": op_name,
                    "params": params,
                    "target_columns": [params["column"]] if "column" in params else params.get("columns", []),
                    "reason": lp.get("reason", "LLM-suggested optimization."),
                    "severity": lp.get("severity", "info"),
                    "source": "llm",
                    "confidence": lp.get("confidence", 0.85),
                    "impact_preview": {},
                })
                existing_signatures.add(sig)

        # Base version 1
        if not dataset.versions:
            raise ValueError(f"Dataset {dataset_id} has no base version.")
        base_version = dataset.versions[0]

        created = await self.repo.create_proposals(dataset_id, base_version.id, combined_props)
        await self.dataset_repo.update_status(dataset_id, "review")
        return created

    async def list_proposals(self, dataset_id: uuid.UUID) -> Sequence[CleaningProposal]:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")
        return await self.repo.list_proposals(dataset_id)

    async def update_proposal_status(
        self,
        dataset_id: uuid.UUID,
        proposal_id: uuid.UUID,
        status: str,
        edited_params: dict[str, Any] | None = None,
    ) -> CleaningProposal | None:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")
        return await self.repo.update_status(dataset_id, proposal_id, status, edited_params)

    async def bulk_update_status(
        self,
        dataset_id: uuid.UUID,
        proposal_ids: list[uuid.UUID],
        status: str,
    ) -> int:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")
        return await self.repo.bulk_update_status(dataset_id, proposal_ids, status)
