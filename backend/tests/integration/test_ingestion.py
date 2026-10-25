import io
import uuid

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl.worksheet.worksheet import Worksheet

from app.main import app
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_full_ingestion_and_event_streaming() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        email = f"ingest_user_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Request upload URL
        up_res = await client.post(
            "/api/v1/datasets/upload-url",
            headers=headers,
            json={"filename": "transactions.csv", "file_size_bytes": 1024},
        )
        assert up_res.status_code == 200
        up_data = up_res.json()
        s3_key = up_data["s3_key"]

        # Put real CSV into MinIO
        storage = StorageService()
        csv_data = (
            b"txn_id,customer_name,amount,status\n"
            b"TX101,John Doe,150.00,completed\n"
            b"TX102,Jane Smith,299.99,pending\n"
            b"TX103,Bob Jones,50.25,failed\n"
        )
        storage.put_object_bytes(s3_key, csv_data, "text/csv")

        # Create dataset
        create_res = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "Transactions 2026",
                "source_filename": "transactions.csv",
                "s3_key": s3_key,
                "description": "Financial ledger",
            },
        )
        assert create_res.status_code == 201
        dataset_id = create_res.json()["id"]

        # Trigger ingestion
        ingest_res = await client.post(
            f"/api/v1/jobs/datasets/{dataset_id}/ingest",
            headers=headers,
        )
        assert ingest_res.status_code == 200
        job_data = ingest_res.json()
        assert job_data["status"] == "succeeded"
        assert job_data["progress"] == 100

        # Verify dataset updated to status 'ready'
        ds_res = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert ds_res.status_code == 200
        ds_data = ds_res.json()
        assert ds_data["status"] == "uploaded"
        assert len(ds_data["versions"]) == 1
        v1 = ds_data["versions"][0]
        assert v1["format"] == "csv"
        assert v1["row_count"] == 3
        assert v1["col_count"] == 4
        assert len(v1["sha256"]) == 64  # valid sha256 hex string

        # Verify raw file exists in S3
        assert storage.object_exists(s3_key)
        raw_stored_bytes = storage.get_object_bytes(s3_key)
        assert len(raw_stored_bytes) == v1["size_bytes"]

        # Verify cached normalized parquet exists in S3
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me_res.json()["id"]
        norm_key = f"datasets/{user_id}/{dataset_id}/normalized.parquet"
        assert storage.object_exists(norm_key)


@pytest.mark.asyncio
async def test_excel_ingestion_and_password_validation() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test password validation error message structure (<8 characters)
        short_pwd_res = await client.post(
            "/api/v1/auth/register",
            json={"email": "shortpwd@example.com", "password": "short"},
        )
        assert short_pwd_res.status_code == 422
        err_envelope = short_pwd_res.json()
        assert "error" in err_envelope
        assert "Password" in err_envelope["error"]["message"]
        assert "at least 8" in err_envelope["error"]["message"]

        # 2. Register with valid credentials
        email = f"excel_user_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePassword123!"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create real Excel workbook bytes (.xlsx)
        wb = openpyxl.Workbook()
        ws = wb.active
        assert isinstance(ws, Worksheet)
        ws.title = "HR Records"
        ws.append(["Emp_ID", "Candidate_Name", "Role", "Experience_Years", "Salary"])
        ws.append([1001, "Alice Brown", "Analyst", 3, 75000])
        ws.append([1002, "Bob Smith", "Senior Analyst", 6, 110000])
        ws.append([1003, "Charlie Davis", "Data Engineer", 4, 95000])

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_bytes = excel_buf.getvalue()

        # Request upload URL for excel file
        up_res = await client.post(
            "/api/v1/datasets/upload-url",
            headers=headers,
            json={
                "filename": "Dr. Ambedkar Institute of Technology Mu-Sigma From HR.xlsx",
                "file_size_bytes": len(excel_bytes),
            },
        )
        assert up_res.status_code == 200
        s3_key = up_res.json()["s3_key"]

        # Upload bytes to storage
        storage = StorageService()
        storage.put_object_bytes(
            s3_key,
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Create dataset
        create_res = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "Mu-Sigma HR Records",
                "source_filename": "Dr. Ambedkar Institute of Technology Mu-Sigma From HR.xlsx",
                "s3_key": s3_key,
                "description": "Campus recruitment dataset",
            },
        )
        assert create_res.status_code == 201
        dataset_id = create_res.json()["id"]

        # Ingest dataset (tests fastexcel + openpyxl fallback ingestion pipeline)
        ingest_res = await client.post(
            f"/api/v1/jobs/datasets/{dataset_id}/ingest",
            headers=headers,
        )
        assert ingest_res.status_code == 200
        job_data = ingest_res.json()
        assert job_data["status"] == "succeeded"
        assert job_data["progress"] == 100

        # Verify dataset metadata and normalized parquet
        ds_res = await client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        assert ds_res.status_code == 200
        ds_data = ds_res.json()
        v1 = ds_data["versions"][0]
        assert v1["format"] == "xlsx"
        assert v1["row_count"] == 3
        assert v1["col_count"] == 5

