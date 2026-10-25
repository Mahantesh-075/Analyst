"""Export service coordinating safe CSV, Parquet, Python, and SQL script generation."""

from __future__ import annotations

import io
import uuid
from typing import Any

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.db.repositories.dataset import DatasetRepository
from app.db.repositories.proposal import ProposalRepository
from app.export.csv import export_formula_safe_csv
from app.ops.registry import (
    compile_pipeline_to_python,
    compile_pipeline_to_sql,
    parse_transform_step,
)
from app.services.storage import StorageService


class ExportService:
    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self.session = session
        self.owner_id = owner_id
        self.dataset_repo = DatasetRepository(session, owner_id)
        self.proposal_repo = ProposalRepository(session, owner_id)
        self.storage = StorageService()

    def _get_active_parquet_bytes(self, dataset: Any) -> bytes:
        if not dataset.versions:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Dataset {dataset.id} has no registered versions",
                status_code=404,
            )

        # Check for cleaned version (version 2)
        target_version = None
        for v in dataset.versions:
            if v.kind == "cleaned":
                target_version = v
                break

        if not target_version:
            target_version = dataset.versions[0]

        if target_version.format == "parquet" and self.storage.object_exists(target_version.storage_key):
            return self.storage.get_object_bytes(target_version.storage_key)

        norm_key = f"datasets/{self.owner_id}/{dataset.id}/normalized.parquet"
        if self.storage.object_exists(norm_key):
            return self.storage.get_object_bytes(norm_key)

        if self.storage.object_exists(target_version.storage_key):
            raw = self.storage.get_object_bytes(target_version.storage_key)
            if raw.startswith(b"PAR1"):
                return raw

        raise AppException(
            code=ErrorCode.NOT_FOUND,
            message="Cleaned data file not found in storage",
            status_code=404,
        )

    async def export_csv(self, dataset_id: uuid.UUID) -> tuple[bytes, str, str]:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        parquet_bytes = self._get_active_parquet_bytes(dataset)
        df = pl.read_parquet(io.BytesIO(parquet_bytes))
        csv_bytes = export_formula_safe_csv(df)
        filename = f"{dataset.name.replace(' ', '_').lower()}_clean.csv"
        return csv_bytes, "text/csv; charset=utf-8", filename

    async def export_parquet(self, dataset_id: uuid.UUID) -> tuple[bytes, str, str]:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        parquet_bytes = self._get_active_parquet_bytes(dataset)
        filename = f"{dataset.name.replace(' ', '_').lower()}_clean.parquet"
        return parquet_bytes, "application/vnd.apache.parquet", filename

    async def export_python_script(self, dataset_id: uuid.UUID) -> tuple[str, str, str]:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        transform_steps = await self.proposal_repo.get_transform_steps(dataset_id)

        ops = [parse_transform_step({"op": s.op, "params": s.params}) for s in transform_steps]

        source_file = dataset.source_filename
        clean_name = dataset.name.replace(" ", "_").lower()
        py_code = compile_pipeline_to_python(
            ops,
            raw_file_path=source_file,
            output_parquet_path=f"cleaned_{clean_name}.parquet",
        )
        filename = f"reproduce_{clean_name}.py"
        return py_code, "text/x-python", filename

    async def export_sql_script(self, dataset_id: uuid.UUID) -> tuple[str, str, str]:
        dataset = await self.dataset_repo.get_dataset(dataset_id)
        transform_steps = await self.proposal_repo.get_transform_steps(dataset_id)

        ops = [parse_transform_step({"op": s.op, "params": s.params}) for s in transform_steps]

        clean_name = dataset.name.replace(" ", "_").lower()
        table_source = f"read_csv('{dataset.source_filename}')"
        sql_code = compile_pipeline_to_sql(ops, raw_table=table_source)
        filename = f"reproduce_{clean_name}.sql"
        return sql_code, "text/x-sql", filename
