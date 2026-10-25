"""Integration test for proposal generation, review, and atomic apply workflow."""

import uuid

import pytest
from httpx import AsyncClient

from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_proposals_generate_and_apply_lifecycle(async_client: AsyncClient) -> None:
    # 1. Register and login
    email = f"cleaner_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Data Cleaner"},
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload messy CSV: trailing spaces, missing tokens "N/A", duplicate rows
    csv_content = (
        "name,age,email\n"
        "  Alice  ,25,alice@example.com\n"
        "Bob,N/A,bob@example.com\n"
        "  Alice  ,25,alice@example.com\n"  # Duplicate row
        "Charlie,30,charlie@example.com\n"
    )

    # 2. Get upload URL and seed messy CSV
    up_resp = await async_client.post(
        "/api/v1/datasets/upload-url",
        headers=headers,
        json={"filename": "messy.csv", "file_size_bytes": len(csv_content)},
    )
    assert up_resp.status_code == 200
    s3_key = up_resp.json()["s3_key"]

    storage = StorageService()
    storage.put_object_bytes(s3_key, csv_content.encode("utf-8"), "text/csv")

    create_ds = await async_client.post(
        "/api/v1/datasets",
        headers=headers,
        json={
            "name": "Messy Users",
            "source_filename": "messy.csv",
            "s3_key": s3_key,
            "description": "Test dataset with defects",
        },
    )
    assert create_ds.status_code == 201
    dataset_id = create_ds.json()["id"]

    # Ingest and profile
    ingest_resp = await async_client.post(
        f"/api/v1/jobs/datasets/{dataset_id}/ingest",
        headers=headers,
    )
    assert ingest_resp.status_code == 200

    profile_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/profile", headers=headers)
    assert profile_resp.status_code == 200

    # 3. Generate cleaning proposals
    gen_resp = await async_client.post(f"/api/v1/datasets/{dataset_id}/proposals/generate", headers=headers)
    assert gen_resp.status_code == 200, f"Generate proposals error: {gen_resp.status_code} {gen_resp.text}"
    proposals = gen_resp.json()
    assert len(proposals) > 0

    op_names = [p["op"] for p in proposals]
    # Check that deduplicate, trim_whitespace, standardize_missing, or mask_pii were proposed
    assert any(op in op_names for op in ["trim_whitespace", "drop_duplicates", "standardize_missing", "mask_pii"])

    # 4. Accept all proposals
    proposal_ids = [p["id"] for p in proposals]
    bulk_resp = await async_client.post(
        f"/api/v1/datasets/{dataset_id}/proposals/bulk",
        headers=headers,
        json={"proposal_ids": proposal_ids, "status": "accepted"},
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["updated"] == len(proposal_ids)

    # 5. Apply proposals
    apply_resp = await async_client.post(f"/api/v1/datasets/{dataset_id}/apply", headers=headers)
    assert apply_resp.status_code == 200
    apply_data = apply_resp.json()
    assert apply_data["status"] == "cleaned"
    assert apply_data["version_number"] == 2
    assert apply_data["kind"] == "cleaned"
    assert apply_data["row_count"] > 0
    assert apply_data["sha256"] != ""

    # 6. Verify cross-user isolation: another user gets 404
    other_email = f"other_{uuid.uuid4().hex[:8]}@example.com"
    other_reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "password": password, "full_name": "Other User"},
    )
    other_token = other_reg.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    other_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/proposals", headers=other_headers)
    assert other_resp.status_code == 404
