import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_profiling_api_and_masked_sample() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        email = f"prof_user_{uuid.uuid4().hex[:8]}@example.com"
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
            json={"filename": "donors.csv", "file_size_bytes": 1024},
        )
        s3_key = up_res.json()["s3_key"]

        # Put CSV into MinIO with PII and outliers
        storage = StorageService()
        csv_data = (
            b"donor_id,donor_name,email,donation_amount,notes\n"
            b"D1,Rahul Sharma,rahul@charity.org,500.0,Annual gift\n"
            b"D2,Sunita Patel,sunita@ngo.org,100.0,N/A\n"
            b"D3,Priya Sen,priya@donor.com,50000.0,-\n"
        )
        storage.put_object_bytes(s3_key, csv_data, "text/csv")

        # Create dataset
        create_res = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "Donor Records",
                "source_filename": "donors.csv",
                "s3_key": s3_key,
            },
        )
        assert create_res.status_code == 201
        dataset_id = create_res.json()["id"]

        # Query Profile
        prof_res = await client.get(
            f"/api/v1/datasets/{dataset_id}/profile",
            headers=headers,
        )
        assert prof_res.status_code == 200
        prof_data = prof_res.json()
        assert prof_data["summary"]["total_rows"] == 3
        assert prof_data["summary"]["total_cols"] == 5
        assert len(prof_data["column_profiles"]) == 5

        # Query Masked Sample
        sample_res = await client.get(
            f"/api/v1/datasets/{dataset_id}/sample",
            headers=headers,
        )
        assert sample_res.status_code == 200
        sample_data = sample_res.json()
        assert len(sample_data["rows"]) == 3
        # Ensure email is masked
        first_row = sample_data["rows"][0]
        assert "***@" in first_row["email"]
        assert "rahul@charity.org" not in first_row["email"]
