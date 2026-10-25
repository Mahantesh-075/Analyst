import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_cross_user_isolation_returns_404() -> None:
    """Security Invariant: Any request accessing another user's dataset must return

    a 404 NOT_FOUND (never a 403 FORBIDDEN to prevent resource enumeration).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register User A
        email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
        reg_a = await client.post(
            "/api/v1/auth/register",
            json={"email": email_a, "password": "PasswordA123!"},
        )
        assert reg_a.status_code == 201
        token_a = reg_a.json()["access_token"]

        # 2. Register User B
        email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
        reg_b = await client.post(
            "/api/v1/auth/register",
            json={"email": email_b, "password": "PasswordB123!"},
        )
        assert reg_b.status_code == 201
        token_b = reg_b.json()["access_token"]

        # 3. User A requests upload URL and creates a dataset
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        upload_req = await client.post(
            "/api/v1/datasets/upload-url",
            headers=headers_a,
            json={"filename": "customers.csv", "file_size_bytes": 1024},
        )
        assert upload_req.status_code == 200
        upload_data = upload_req.json()
        s3_key = upload_data["s3_key"]

        # Seed the object in MinIO storage
        storage = StorageService()
        storage.put_object_bytes(s3_key, b"id,name\n1,Alice\n2,Bob", "text/csv")

        # User A completes dataset registration
        create_res = await client.post(
            "/api/v1/datasets",
            headers=headers_a,
            json={
                "name": "Customer Records",
                "source_filename": "customers.csv",
                "s3_key": s3_key,
                "description": "Sensitive customer data",
            },
        )
        assert create_res.status_code == 201
        dataset_a_id = create_res.json()["id"]

        # 4. User B attempts GET on User A's dataset -> MUST return 404
        get_res = await client.get(
            f"/api/v1/datasets/{dataset_a_id}",
            headers=headers_b,
        )
        assert get_res.status_code == 404
        assert get_res.json()["error"]["code"] == "NOT_FOUND"

        # 5. User B attempts PATCH on User A's dataset -> MUST return 404
        patch_res = await client.patch(
            f"/api/v1/datasets/{dataset_a_id}",
            headers=headers_b,
            json={"name": "Hacked Name"},
        )
        assert patch_res.status_code == 404
        assert patch_res.json()["error"]["code"] == "NOT_FOUND"

        # 6. User B attempts DELETE on User A's dataset -> MUST return 404
        del_res = await client.delete(
            f"/api/v1/datasets/{dataset_a_id}",
            headers=headers_b,
        )
        assert del_res.status_code == 404
        assert del_res.json()["error"]["code"] == "NOT_FOUND"

        # 7. User B lists datasets -> User A's dataset must NOT appear
        list_b = await client.get("/api/v1/datasets", headers=headers_b)
        assert list_b.status_code == 200
        assert list_b.json()["total"] == 0
        assert len(list_b.json()["items"]) == 0

        # 8. User A can still retrieve, update, and soft-delete their dataset
        get_a = await client.get(f"/api/v1/datasets/{dataset_a_id}", headers=headers_a)
        assert get_a.status_code == 200
        assert get_a.json()["name"] == "Customer Records"

        del_a = await client.delete(f"/api/v1/datasets/{dataset_a_id}", headers=headers_a)
        assert del_a.status_code == 204

        # After soft delete, User A also gets 404
        get_a_deleted = await client.get(f"/api/v1/datasets/{dataset_a_id}", headers=headers_a)
        assert get_a_deleted.status_code == 404
