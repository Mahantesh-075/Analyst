"""Integration test for Milestone 6: Dashboard visualisations, safe query builder, and Invariant 3 narratives."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import pytest
from httpx import AsyncClient

from app.services.storage import StorageService

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "schemas"


@pytest.mark.asyncio
async def test_dashboard_and_query_builder_lifecycle(async_client: AsyncClient) -> None:
    # 1. Register and login
    email = f"analyst_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Senior Analyst"},
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload structured sales dataset
    csv_content = (
        "region,sales,units,category\n"
        "North,5000.0,50,Electronics\n"
        "South,3200.5,30,Apparel\n"
        "North,4500.0,40,Electronics\n"
        "East,2800.0,25,Furniture\n"
        "West,6100.0,60,Electronics\n"
    )

    up_resp = await async_client.post(
        "/api/v1/datasets/upload-url",
        headers=headers,
        json={"filename": "sales.csv", "file_size_bytes": len(csv_content)},
    )
    assert up_resp.status_code == 200
    s3_key = up_resp.json()["s3_key"]

    storage = StorageService()
    storage.put_object_bytes(s3_key, csv_content.encode("utf-8"), "text/csv")

    create_ds = await async_client.post(
        "/api/v1/datasets",
        headers=headers,
        json={
            "name": "Regional Sales 2026",
            "source_filename": "sales.csv",
            "s3_key": s3_key,
            "description": "Sales analysis dataset",
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

    # 3. Generate and retrieve Dashboard
    dash_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/dashboard", headers=headers)
    assert dash_resp.status_code == 200, f"Dashboard error: {dash_resp.status_code} {dash_resp.text}"
    dash_data = dash_resp.json()

    # Validate schema conformity against schemas/chart_spec.schema.json
    schema_path = SCHEMAS_DIR / "chart_spec.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    # Validate pure spec portion
    jsonschema.validate(instance=dash_data["spec"], schema=schema)

    # Check KPIs
    assert len(dash_data["kpis"]) >= 1
    total_rec_kpi = next(k for k in dash_data["kpis"] if k["id"] == "total_records")
    assert total_rec_kpi["computed_value"] == 5

    # Check Charts
    assert len(dash_data["charts"]) >= 1
    for chart in dash_data["charts"]:
        assert "data" in chart
        assert "columns" in chart["data"]
        assert "rows" in chart["data"]

    # Check Narratives
    assert len(dash_data["narratives_rendered"]) >= 1
    assert any("5" in n for n in dash_data["narratives_rendered"])

    # 4. Safe Query Builder endpoint
    query_payload = {
        "dimensions": [{"field": "region"}],
        "measures": [
            {"field": "*", "agg": "count", "as": "cnt"},
            {"field": "sales", "agg": "sum", "as": "total_sales"},
        ],
        "order_by": [{"field": "total_sales", "dir": "desc"}],
        "limit": 10,
    }
    q_resp = await async_client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json=query_payload,
    )
    assert q_resp.status_code == 200
    q_res = q_resp.json()
    assert q_res["columns"] == ["region", "cnt", "total_sales"]
    assert len(q_res["rows"]) == 4  # North, West, South, East
    north_row = next(r for r in q_res["rows"] if r["region"] == "North")
    assert north_row["cnt"] == 2
    assert north_row["total_sales"] == 9500.0

    # 5. Safe Query Injection Attempt (Rejection)
    bad_query = {
        "dimensions": [{"field": "region; DROP TABLE users;"}],
        "measures": [{"field": "*", "agg": "count", "as": "cnt"}],
    }
    bad_resp = await async_client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json=bad_query,
    )
    assert bad_resp.status_code == 400
    assert "Unauthorized column" in bad_resp.json()["detail"]

    # 6. Cross-User Isolation (Return 404, never 403)
    other_email = f"unauth_{uuid.uuid4().hex[:8]}@example.com"
    other_reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "password": password, "full_name": "Unauthorized User"},
    )
    other_token = other_reg.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    iso_dash = await async_client.get(f"/api/v1/datasets/{dataset_id}/dashboard", headers=other_headers)
    assert iso_dash.status_code == 404

    iso_query = await async_client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=other_headers,
        json=query_payload,
    )
    assert iso_query.status_code == 404
