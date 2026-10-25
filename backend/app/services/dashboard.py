"""Dashboard orchestration service managing safe queries, deterministic charts, and Invariant 3 narratives."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard.generator import compute_dashboard_data, generate_dashboard_spec
from app.dashboard.narratives import render_narrative
from app.dashboard.query_builder import execute_safe_query
from app.db.repositories.dataset import DatasetRepository
from app.db.repositories.profile import ProfileRepository
from app.schemas.dashboard import DashboardResponse, SafeQueryResult
from app.services.profiling import ProfilingService
from app.services.storage import StorageService


class DashboardService:
    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self.session = session
        self.owner_id = owner_id
        self.dataset_repo = DatasetRepository(session, owner_id)
        self.profile_repo = ProfileRepository(session)
        self.profiling_service = ProfilingService(session, owner_id)
        self.storage = StorageService()

    def _load_parquet_bytes(self, dataset_id: uuid.UUID, version: Any) -> bytes:
        if getattr(version, "format", "") == "parquet" and self.storage.object_exists(version.storage_key):
            return self.storage.get_object_bytes(version.storage_key)

        norm_key = f"datasets/{self.owner_id}/{dataset_id}/normalized.parquet"
        if self.storage.object_exists(norm_key):
            return self.storage.get_object_bytes(norm_key)

        if self.storage.object_exists(version.storage_key):
            raw = self.storage.get_object_bytes(version.storage_key)
            if raw.startswith(b"PAR1"):
                return raw

        raise ValueError(f"Normalized Parquet file for dataset {dataset_id} could not be located in storage.")

    async def get_dashboard(self, dataset_id: uuid.UUID) -> DashboardResponse:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")

        # Determine target version (prefer current_version_id, or version 2 cleaned, or version 1 raw)
        target_version = None
        if dataset.current_version_id and dataset.versions:
            for v in dataset.versions:
                if v.id == dataset.current_version_id:
                    target_version = v
                    break

        if not target_version and dataset.versions:
            # Pick highest version_no
            target_version = sorted(dataset.versions, key=lambda v: v.version_no, reverse=True)[0]

        if not target_version:
            raise ValueError(f"Dataset {dataset_id} has no registered versions.")

        # Retrieve profile
        ds_profile = await self.profile_repo.get_by_version_id(target_version.id)
        if not ds_profile:
            ds_profile = await self.profiling_service.profile_dataset(dataset_id, target_version.id)

        # Retrieve Parquet bytes
        parquet_bytes = self._load_parquet_bytes(dataset_id, target_version)

        col_profiles = [
            {
                "name": c.name,
                "inferred_dtype": c.inferred_dtype,
                "stats": c.stats,
                "null_pct": c.null_pct,
                "distinct_count": c.distinct_count,
            }
            for c in ds_profile.column_profiles
        ]
        allowed_columns: set[str] = {str(c["name"]) for c in col_profiles}

        # Generate deterministic spec
        spec = generate_dashboard_spec(
            dataset_name=dataset.name,
            column_profiles=col_profiles,
            total_rows=ds_profile.summary.get("total_rows", 0) if ds_profile.summary else 0,
        )

        # Compute live data for KPIs and charts
        computed = compute_dashboard_data(spec, parquet_bytes, allowed_columns)

        # Render narratives with deterministic formatting
        rendered_narratives: list[str] = []
        kpi_formats = {k["id"]: k.get("format", "decimal") for k in spec.get("kpis", [])}
        for n in spec.get("narrative", []):
            rendered = render_narrative(n["template"], computed["kpi_values"], kpi_formats)
            rendered_narratives.append(rendered)

        return DashboardResponse(
            dataset_id=str(dataset_id),
            version_id=str(target_version.id),
            spec=spec,
            kpis=computed["kpis"],
            charts=computed["charts"],
            narratives_rendered=rendered_narratives,
        )

    async def execute_custom_query(
        self,
        dataset_id: uuid.UUID,
        query_dict: dict[str, Any],
    ) -> SafeQueryResult:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")

        if not dataset.versions:
            raise ValueError(f"Dataset {dataset_id} has no registered versions.")

        target_version = sorted(dataset.versions, key=lambda v: v.version_no, reverse=True)[0]
        ds_profile = await self.profile_repo.get_by_version_id(target_version.id)
        if not ds_profile:
            raise ValueError(f"Dataset {dataset_id} must be profiled before running queries.")

        allowed_columns = {c.name for c in ds_profile.column_profiles}

        parquet_bytes = self._load_parquet_bytes(dataset_id, target_version)

        res = execute_safe_query(parquet_bytes, query_dict, allowed_columns)
        return SafeQueryResult(
            columns=res["columns"],
            rows=res["rows"],
            row_count=res["row_count"],
        )
