from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppException, ErrorCode
from app.db.models.dataset import Dataset, DatasetVersion
from app.db.repositories.base import ScopedRepository


class DatasetRepository(ScopedRepository[Dataset]):
    def __init__(self, session: AsyncSession, owner_id: UUID) -> None:
        super().__init__(Dataset, session, owner_id)

    async def list_datasets(
        self,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> tuple[list[Dataset], int]:
        base_query = select(Dataset).where(Dataset.owner_id == self.owner_id)
        if not include_deleted:
            base_query = base_query.where(Dataset.deleted_at.is_(None))

        if search:
            pattern = f"%{search.strip()}%"
            base_query = base_query.where(
                Dataset.name.ilike(pattern) | Dataset.description.ilike(pattern)
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_count = (await self.session.execute(count_query)).scalar() or 0

        # Query items with eager versions
        items_query = (
            base_query.options(selectinload(Dataset.versions))
            .order_by(Dataset.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(items_query)
        items = list(result.scalars().all())
        return items, total_count

    async def get_dataset(
        self, dataset_id: UUID, include_deleted: bool = False
    ) -> Dataset:
        query = (
            select(Dataset)
            .options(selectinload(Dataset.versions))
            .where(Dataset.owner_id == self.owner_id, Dataset.id == dataset_id)
        )
        if not include_deleted:
            query = query.where(Dataset.deleted_at.is_(None))

        result = await self.session.execute(query)
        dataset = result.scalars().first()
        if not dataset:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Dataset {dataset_id} not found",
                status_code=404,
            )
        return dataset

    async def create_dataset(
        self,
        name: str,
        source_filename: str,
        description: str | None = None,
        parse_settings: dict[str, Any] | None = None,
        retention_days: int = 30,
    ) -> Dataset:
        retention_until = datetime.now(UTC).replace(microsecond=0) + timedelta(days=retention_days)
        dataset = Dataset(
            owner_id=self.owner_id,
            name=name,
            source_filename=source_filename,
            description=description,
            parse_settings=parse_settings or {},
            status="uploaded",
            retention_until=retention_until,
        )
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def soft_delete(self, dataset_id: UUID) -> None:
        dataset = await self.get_dataset(dataset_id)
        dataset.deleted_at = datetime.now(UTC)
        await self.session.flush()

    async def restore(self, dataset_id: UUID) -> Dataset:
        dataset = await self.get_dataset(dataset_id, include_deleted=True)
        dataset.deleted_at = None
        await self.session.flush()
        return dataset

    async def update_status(
        self, dataset_id: UUID, status: str, current_version_id: UUID | None = None
    ) -> Dataset:
        dataset = await self.get_dataset(dataset_id)
        dataset.status = status
        if current_version_id is not None:
            dataset.current_version_id = current_version_id
        await self.session.flush()
        return dataset


class DatasetVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_version(
        self,
        dataset_id: UUID,
        version_no: int,
        kind: str,
        storage_key: str,
        format: str,
        size_bytes: int,
        sha256: str,
        parent_version_id: UUID | None = None,
        row_count: int | None = None,
        col_count: int | None = None,
    ) -> DatasetVersion:
        version = DatasetVersion(
            dataset_id=dataset_id,
            version_no=version_no,
            kind=kind,
            storage_key=storage_key,
            format=format,
            size_bytes=size_bytes,
            sha256=sha256,
            parent_version_id=parent_version_id,
            row_count=row_count,
            col_count=col_count,
        )
        self.session.add(version)
        await self.session.flush()

        # Update dataset current_version_id
        await self.session.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(current_version_id=version.id, status="cleaned" if kind == "cleaned" else "uploaded")
        )
        await self.session.flush()
        return version

    async def get_version(self, version_id: UUID) -> DatasetVersion | None:
        query = select(DatasetVersion).where(DatasetVersion.id == version_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_latest_version(self, dataset_id: UUID) -> DatasetVersion | None:
        query = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_no.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()
