import hashlib
import io
import json
from typing import Any
from uuid import UUID

import polars as pl
import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.db.models.dataset import Dataset
from app.db.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.services.excel_reader import read_excel_safe
from app.services.sniffer import SnifferService
from app.services.storage import StorageService

logger = structlog.get_logger("service.ingestion")

MAX_ROWS = 2_000_000
MAX_COLS = 500


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        storage: StorageService | None = None,
        sniffer: SnifferService | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.storage = storage or StorageService()
        self.sniffer = sniffer or SnifferService()
        self.dataset_repo = DatasetRepository(session, user_id)
        self.version_repo = DatasetVersionRepository(session)

    async def emit_progress(
        self,
        job_id: UUID,
        progress: int,
        status: str,
        message: str,
        redis_client: Any | None = None,
    ) -> None:
        """Publish progress event to Redis for SSE streaming."""
        payload = {
            "job_id": str(job_id),
            "progress": progress,
            "status": status,
            "message": message,
        }
        try:
            r = redis_client or aioredis.from_url(settings.REDIS_URL)
            await r.publish(f"job:{job_id}:events", json.dumps(payload))
            if not redis_client:
                await r.close()
        except Exception as e:
            logger.warning("redis_publish_failed", error=str(e), job_id=str(job_id))

    def parse_to_polars(
        self,
        raw_bytes: bytes,
        source_filename: str,
        parse_settings: dict[str, Any],
    ) -> pl.DataFrame:
        """Parse raw file bytes into a Polars DataFrame with safety caps."""
        lower_name = source_filename.lower()
        fmt = parse_settings.get("format")
        if not fmt:
            if lower_name.endswith((".xlsx", ".xls")):
                fmt = "xlsx"
            elif lower_name.endswith(".parquet"):
                fmt = "parquet"
            else:
                fmt = "csv"

        try:
            if fmt == "xlsx":
                sheet = parse_settings.get("sheet") or None
                df = read_excel_safe(raw_bytes, sheet_name=sheet)
            elif fmt == "parquet":
                df = pl.read_parquet(io.BytesIO(raw_bytes))
            else:
                # CSV / TSV
                sep = parse_settings.get("delimiter", ",")
                encoding = parse_settings.get("encoding", "utf-8")
                skip_rows = parse_settings.get("header_row", 0)

                df = pl.read_csv(
                    io.BytesIO(raw_bytes),
                    separator=sep,
                    encoding=encoding,
                    skip_rows=skip_rows,
                    infer_schema_length=10000,
                    null_values=["", "NA", "N/A", "null", "NULL", "None", "NaN"],
                    truncate_ragged_lines=True,
                )
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"Failed to parse tabular file: {str(e)}",
                status_code=400,
            ) from e

        # Enforce column cap
        if df.width > MAX_COLS:
            raise AppException(
                code=ErrorCode.DATASET_TOO_LARGE,
                message=f"Dataset has {df.width} columns, exceeding limit of {MAX_COLS}",
                status_code=413,
            )

        # Enforce row cap
        if df.height > MAX_ROWS:
            raise AppException(
                code=ErrorCode.DATASET_TOO_LARGE,
                message=f"Dataset has {df.height} rows, exceeding limit of {MAX_ROWS}",
                status_code=413,
            )

        # Sanitize column names: strip whitespace, ensure non-empty
        clean_cols = []
        for i, col in enumerate(df.columns):
            name = col.strip() or f"col_{i+1}"
            clean_cols.append(name)
        df.columns = clean_cols

        return df

    async def ingest_dataset(
        self,
        dataset_id: UUID,
        job_id: UUID | None = None,
    ) -> Dataset:
        """Full ingestion pipeline: sniff, parse, normalize to Parquet, commit version 1."""
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        if not dataset.versions:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="Dataset has no registered versions",
                status_code=404,
            )

        raw_ver = dataset.versions[0]
        logger.info("ingest_started", dataset_id=str(dataset_id), raw_key=raw_ver.storage_key)

        if job_id:
            await self.emit_progress(job_id, 10, "running", "Inspecting file safety and format")

        # 1. Fetch raw bytes
        raw_bytes = self.storage.get_object_bytes(raw_ver.storage_key)

        # 2. Safety inspection & Sniffing
        detected = self.sniffer.sniff(raw_bytes, dataset.source_filename)
        combined_settings = {**detected, **(dataset.parse_settings or {})}
        dataset.parse_settings = combined_settings

        if job_id:
            await self.emit_progress(job_id, 40, "running", "Parsing rows into tabular engine")

        # 3. Parse with Polars and enforce caps
        df = self.parse_to_polars(raw_bytes, dataset.source_filename, combined_settings)

        if job_id:
            await self.emit_progress(job_id, 70, "running", "Serializing to normalized Parquet")

        # 4. Serialize to Parquet
        parquet_buf = io.BytesIO()
        df.write_parquet(parquet_buf, compression="snappy")
        parquet_bytes = parquet_buf.getvalue()
        canonical_sha256 = hashlib.sha256(parquet_bytes).hexdigest()

        # 5. Store cached normalized Parquet for fast query/profiling
        norm_key = f"datasets/{self.user_id}/{dataset_id}/normalized.parquet"
        self.storage.put_object_bytes(norm_key, parquet_bytes, "application/vnd.apache.parquet")

        # 6. Update Dataset parse_settings and updated_at
        dataset.status = "uploaded"
        await self.session.flush()

        if job_id:
            await self.emit_progress(job_id, 100, "succeeded", "Dataset ingested successfully")

        logger.info(
            "ingest_completed",
            dataset_id=str(dataset_id),
            rows=df.height,
            cols=df.width,
            sha256=canonical_sha256,
        )
        return await self.dataset_repo.get_dataset(dataset_id)
