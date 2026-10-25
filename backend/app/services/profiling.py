import io
from typing import Any
from uuid import UUID

import polars as pl
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.db.models.profile import Profile
from app.db.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.db.repositories.profile import ProfileRepository
from app.profiling.engine import ProfilingEngine
from app.services.excel_reader import read_excel_safe
from app.services.storage import StorageService

logger = structlog.get_logger("service.profiling")
ENGINE_VERSION = "polars-1.20-deterministic"


class ProfilingService:
    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        storage: StorageService | None = None,
        engine: ProfilingEngine | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.storage = storage or StorageService()
        self.engine = engine or ProfilingEngine()
        self.dataset_repo = DatasetRepository(session, user_id)
        self.version_repo = DatasetVersionRepository(session)
        self.profile_repo = ProfileRepository(session)

    async def get_dataframe_for_version(self, dataset_id: UUID, version_no: int = 1) -> pl.DataFrame:
        """Load Polars DataFrame for a dataset version."""
        if version_no == 2:
            cleaned_key = f"datasets/{self.user_id}/{dataset_id}/v2_cleaned.parquet"
            if self.storage.object_exists(cleaned_key):
                parquet_bytes = self.storage.get_object_bytes(cleaned_key)
                return pl.read_parquet(io.BytesIO(parquet_bytes))

        norm_key = f"datasets/{self.user_id}/{dataset_id}/normalized.parquet"
        if self.storage.object_exists(norm_key):
            parquet_bytes = self.storage.get_object_bytes(norm_key)
            return pl.read_parquet(io.BytesIO(parquet_bytes))

        # Fallback to reading raw file with parse settings
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset or not dataset.versions:
            raise AppException(ErrorCode.NOT_FOUND, "No versions registered for dataset", 404)

        ver = dataset.versions[0]
        raw_bytes = self.storage.get_object_bytes(ver.storage_key)
        settings = dataset.parse_settings or {}

        if ver.format == "parquet":
            return pl.read_parquet(io.BytesIO(raw_bytes))
        elif ver.format == "xlsx":
            sheet = settings.get("sheet") or None
            return read_excel_safe(raw_bytes, sheet_name=sheet)
        else:
            return pl.read_csv(
                io.BytesIO(raw_bytes),
                separator=settings.get("delimiter", ","),
                encoding=settings.get("encoding", "utf-8"),
                skip_rows=settings.get("header_row", 0),
                infer_schema_length=10000,
                truncate_ragged_lines=True,
            )

    async def profile_dataset(
        self,
        dataset_id: UUID,
        version_id: UUID | None = None,
    ) -> Profile:
        """Run deterministic profiling and persist to database."""
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset.versions:
            raise AppException(ErrorCode.NOT_FOUND, "Dataset has no registered versions", 404)

        target_version = dataset.versions[0]
        if version_id:
            for v in dataset.versions:
                if v.id == version_id:
                    target_version = v
                    break

        logger.info("profiling_started", dataset_id=str(dataset_id), version_id=str(target_version.id))

        df = await self.get_dataframe_for_version(dataset_id, target_version.version_no)
        profile_data = self.engine.profile_dataframe(df)

        profile = await self.profile_repo.create_profile(
            version_id=target_version.id,
            engine_version=ENGINE_VERSION,
            summary=profile_data["summary"],
            columns_data=profile_data["columns"],
        )

        dataset.status = "profiled"
        await self.session.flush()

        logger.info(
            "profiling_completed",
            dataset_id=str(dataset_id),
            rows=profile_data["summary"]["total_rows"],
            cols=profile_data["summary"]["total_cols"],
            has_pii=profile_data["summary"]["has_pii"],
        )
        return profile

    async def get_profile(self, dataset_id: UUID, version_id: UUID | None = None) -> Profile:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        target_version_id = version_id or dataset.current_version_id
        if not target_version_id:
            if not dataset.versions:
                raise AppException(ErrorCode.NOT_FOUND, "Dataset has no versions", 404)
            target_version_id = dataset.versions[0].id

        profile = await self.profile_repo.get_by_version_id(target_version_id)
        if not profile:
            # Auto-run profile if not yet profiled
            profile = await self.profile_dataset(dataset_id, target_version_id)
        return profile

    async def get_masked_sample(
        self,
        dataset_id: UUID,
        version_id: UUID | None = None,
        n_rows: int = 20,
    ) -> list[dict[str, Any]]:
        """Return exactly n_rows sample guaranteed to have all PII masked."""
        profile = await self.get_profile(dataset_id, version_id)
        df = await self.get_dataframe_for_version(dataset_id)

        columns_profile = [
            {
                "name": cp.name,
                "is_pii": cp.is_pii,
                "pii_types": cp.pii_types,
            }
            for cp in profile.column_profiles
        ]
        return self.engine.generate_masked_sample(df, columns_profile, n_rows=n_rows)
