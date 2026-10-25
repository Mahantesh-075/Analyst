import hashlib
import io
import re
import uuid
from typing import Any
from uuid import UUID

import polars as pl
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.db.models.dataset import Dataset
from app.db.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.services.excel_reader import read_excel_safe
from app.services.sniffer import SnifferService
from app.services.storage import StorageService

logger = structlog.get_logger("service.dataset")


class DatasetService:
    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        storage: StorageService | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.dataset_repo = DatasetRepository(session, user_id)
        self.version_repo = DatasetVersionRepository(session)
        self.storage = storage or StorageService()

    def sanitize_filename(self, filename: str) -> str:
        clean = re.sub(r"[^\w\.\-\_]", "_", filename.strip())
        return clean or "dataset.csv"

    async def generate_upload_url(
        self,
        filename: str,
        file_size_bytes: int,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if file_size_bytes > max_bytes:
            raise AppException(
                code=ErrorCode.DATASET_TOO_LARGE,
                message=f"File size ({file_size_bytes} bytes) exceeds maximum limit of {settings.MAX_UPLOAD_MB} MB",
                status_code=413,
            )

        clean_filename = self.sanitize_filename(filename)
        upload_uuid = uuid.uuid4().hex
        s3_key = f"raw/{self.user_id}/{upload_uuid}/{clean_filename}"

        return self.storage.generate_presigned_upload_url(
            s3_key=s3_key,
            content_type=mime_type,
            max_size_bytes=max_bytes,
        )

    async def create_dataset(
        self,
        name: str,
        source_filename: str,
        s3_key: str,
        description: str | None = None,
        parse_settings: dict[str, Any] | None = None,
    ) -> Dataset:
        # Invariant: Users may only bind datasets to keys within their own user prefix
        expected_prefix = f"raw/{self.user_id}/"
        if not s3_key.startswith(expected_prefix):
            logger.warning("unauthorized_s3_key_binding", user_id=str(self.user_id), s3_key=s3_key)
            raise AppException(
                code=ErrorCode.AUTH_INVALID,
                message="Unauthorized storage reference",
                status_code=403,
            )

        # Verify object exists in S3
        if not self.storage.object_exists(s3_key):
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Uploaded file not found in storage at key: {s3_key}",
                status_code=400,
            )

        # Read object metadata and compute sha256
        meta = self.storage.get_object_metadata(s3_key)
        raw_bytes = self.storage.get_object_bytes(s3_key)
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Content safety and format sniffing
        sniffer = SnifferService()
        sniffer.inspect_safety(raw_bytes, source_filename)
        detected_settings = sniffer.sniff(raw_bytes, source_filename)
        merged_settings = {**detected_settings, **(parse_settings or {})}

        file_format = detected_settings.get("format", "csv")
        row_count = None
        col_count = None
        try:
            if file_format in ["csv", "tsv"]:
                df = pl.read_csv(
                    io.BytesIO(raw_bytes),
                    separator=merged_settings.get("delimiter", ","),
                    encoding=merged_settings.get("encoding", "utf-8"),
                    infer_schema_length=1000,
                    truncate_ragged_lines=True,
                )
                row_count = df.height
                col_count = df.width
            elif file_format == "parquet":
                df = pl.read_parquet(io.BytesIO(raw_bytes))
                row_count = df.height
                col_count = df.width
            elif file_format == "xlsx":
                sheet = merged_settings.get("sheet") or None
                df = read_excel_safe(raw_bytes, sheet_name=sheet)
                row_count = df.height
                col_count = df.width
        except Exception as e:
            logger.warning("initial_counts_failed", error=str(e))

        dataset = await self.dataset_repo.create_dataset(
            name=name,
            source_filename=source_filename,
            description=description,
            parse_settings=merged_settings,
            retention_days=settings.RETENTION_DAYS,
        )

        # Create initial raw version 1
        await self.version_repo.create_version(
            dataset_id=dataset.id,
            version_no=1,
            kind="raw",
            storage_key=s3_key,
            format=file_format,
            size_bytes=meta["content_length"],
            sha256=sha256,
            row_count=row_count,
            col_count=col_count,
        )

        # Reload with versions
        return await self.dataset_repo.get_dataset(dataset.id)

    async def list_datasets(
        self,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Dataset], int]:
        return await self.dataset_repo.list_datasets(
            search=search, skip=skip, limit=limit
        )

    async def get_dataset(self, dataset_id: UUID) -> Dataset:
        return await self.dataset_repo.get_dataset(dataset_id=dataset_id)

    async def update_dataset(
        self,
        dataset_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Dataset:
        dataset = await self.dataset_repo.get_dataset(dataset_id=dataset_id)
        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        await self.session.flush()
        return await self.dataset_repo.get_dataset(dataset_id=dataset_id)

    async def delete_dataset(self, dataset_id: UUID) -> None:
        await self.dataset_repo.soft_delete(dataset_id=dataset_id)
