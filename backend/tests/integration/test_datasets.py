import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_dataset_upload_limits_and_crud() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        email = f"dataset_user_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Size cap enforcement: file > 200MB rejected with 413
        oversized = (settings.MAX_UPLOAD_MB * 1024 * 1024) + 1
        bad_upload = await client.post(
            "/api/v1/datasets/upload-url",
            headers=headers,
            json={"filename": "giant.csv", "file_size_bytes": oversized},
        )
        assert bad_upload.status_code == 413
        assert bad_upload.json()["error"]["code"] == "DATASET_TOO_LARGE"

        # 2. Valid upload URL request
        good_upload = await client.post(
            "/api/v1/datasets/upload-url",
            headers=headers,
            json={"filename": "sales_q3.csv", "file_size_bytes": 5000},
        )
        assert good_upload.status_code == 200
        up_data = good_upload.json()
        assert "upload_url" in up_data
        s3_key = up_data["s3_key"]
        assert f"/{up_data['s3_key'].split('/')[1]}/" in s3_key

        # 3. Create dataset without uploading file fails with 400
        missing_file_res = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "Ghost Dataset",
                "source_filename": "ghost.csv",
                "s3_key": f"raw/{up_data['s3_key'].split('/')[1]}/ghost/file.csv",
            },
        )
        assert missing_file_res.status_code == 400

        # Seed real file in MinIO
        storage = StorageService()
        csv_payload = b"id,product,amount\n1,Widget,19.99\n2,Gadget,49.50"
        storage.put_object_bytes(s3_key, csv_payload, "text/csv")

        # 4. Create dataset successfully
        create_res = await client.post(
            "/api/v1/datasets",
            headers=headers,
            json={
                "name": "Q3 Sales Dataset",
                "source_filename": "sales_q3.csv",
                "s3_key": s3_key,
                "description": "Quarterly sales numbers",
            },
        )
        assert create_res.status_code == 201
        ds = create_res.json()
        dataset_id = ds["id"]
        assert ds["name"] == "Q3 Sales Dataset"
        assert ds["status"] == "uploaded"
        assert len(ds["versions"]) == 1
        assert ds["versions"][0]["version_no"] == 1
        assert ds["versions"][0]["kind"] == "raw"
        assert ds["versions"][0]["size_bytes"] == len(csv_payload)

        # 5. Search datasets
        search_res = await client.get(
            "/api/v1/datasets?search=Sales",
            headers=headers,
        )
        assert search_res.status_code == 200
        assert search_res.json()["total"] == 1
        assert search_res.json()["items"][0]["id"] == dataset_id

        # 6. Update dataset metadata
        patch_res = await client.patch(
            f"/api/v1/datasets/{dataset_id}",
            headers=headers,
            json={"name": "Q3 Sales (Final)", "description": "Audited figures"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["name"] == "Q3 Sales (Final)"
        assert patch_res.json()["description"] == "Audited figures"
