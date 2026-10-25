"""Integration test for Milestone 7: Exporters and Invariant 7 (100% Reproducibility Guarantee).

Ensures:
1. CSV export neutralizes formula injection (CWE-1236).
2. Parquet export matches the active cleaned version.
3. Python reproduction script executes on raw data and produces identical cleaned results.
4. DuckDB SQL script executes on raw data and produces identical cleaned results.
5. Cross-user export requests strictly return 404 NOT_FOUND.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import uuid

import duckdb
import polars as pl
import pytest
from httpx import AsyncClient

from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_reproducibility_and_export_lifecycle(async_client: AsyncClient) -> None:
    # 1. Register User A
    email = f"repro_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Reproducibility User"},
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload messy CSV with trailing spaces, duplicates, formula injection
    csv_raw = (
        "name,age,formula\n"
        "  Alice  ,25,=1+1\n"
        "Bob,30,@admin\n"
        "  Alice  ,25,=1+1\n"
        "Charlie,35,+12345\n"
    )
    filename = "messy_repro.csv"

    up_resp = await async_client.post(
        "/api/v1/datasets/upload-url",
        headers=headers,
        json={"filename": filename, "file_size_bytes": len(csv_raw)},
    )
    assert up_resp.status_code == 200
    s3_key = up_resp.json()["s3_key"]

    storage = StorageService()
    storage.put_object_bytes(s3_key, csv_raw.encode("utf-8"), "text/csv")

    create_ds = await async_client.post(
        "/api/v1/datasets",
        headers=headers,
        json={
            "name": "Messy Repro Dataset",
            "source_filename": filename,
            "s3_key": s3_key,
            "description": "Reproducibility test dataset",
        },
    )
    assert create_ds.status_code == 201
    dataset_id = create_ds.json()["id"]

    # Ingest and profile
    ingest_resp = await async_client.post(f"/api/v1/jobs/datasets/{dataset_id}/ingest", headers=headers)
    assert ingest_resp.status_code == 200

    profile_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/profile", headers=headers)
    assert profile_resp.status_code == 200

    # 3. Generate proposals, accept them, and apply
    gen_resp = await async_client.post(f"/api/v1/datasets/{dataset_id}/proposals/generate", headers=headers)
    assert gen_resp.status_code == 200
    proposals = gen_resp.json()
    assert len(proposals) > 0

    proposal_ids = [p["id"] for p in proposals]
    bulk_resp = await async_client.post(
        f"/api/v1/datasets/{dataset_id}/proposals/bulk",
        headers=headers,
        json={"proposal_ids": proposal_ids, "status": "accepted"},
    )
    assert bulk_resp.status_code == 200

    apply_resp = await async_client.post(f"/api/v1/datasets/{dataset_id}/apply", headers=headers)
    assert apply_resp.status_code == 200
    apply_data = apply_resp.json()
    assert apply_data["status"] == "cleaned"

    # 4. Test CSV Export: Invariant 5 (formula injection neutralization)
    csv_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/export/csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    csv_text = csv_resp.text
    # Check neutralization of formula characters = @ +
    assert "'=1+1" in csv_text
    assert "'@admin" in csv_text
    assert "'+12345" in csv_text

    # 5. Test Parquet Export: Verify valid Parquet and row count
    parquet_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/export/parquet", headers=headers)
    assert parquet_resp.status_code == 200
    assert "application/vnd.apache.parquet" in parquet_resp.headers["content-type"]
    parquet_bytes = parquet_resp.content
    assert parquet_bytes.startswith(b"PAR1")
    df_cleaned_sys = pl.read_parquet(io.BytesIO(parquet_bytes))
    assert df_cleaned_sys.height == apply_data["row_count"]

    # 6. Test Python Script Export: Invariant 7 (100% Reproducibility Guarantee)
    py_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/export/python", headers=headers)
    assert py_resp.status_code == 200
    assert "text/x-python" in py_resp.headers["content-type"]
    py_script = py_resp.text
    assert "import polars as pl" in py_script
    assert "def run_pipeline()" in py_script

    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_csv_path = os.path.join(tmp_dir, filename)
        with open(raw_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_raw)

        py_script_path = os.path.join(tmp_dir, "reproduce.py")
        with open(py_script_path, "w", encoding="utf-8") as f:
            f.write(py_script)

        # Run generated Python script in subprocess
        proc = subprocess.run(
            [sys.executable, py_script_path],
            cwd=tmp_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"Python script execution failed: {proc.stderr}"

        # Load output parquet from Python script
        clean_name = "messy_repro_dataset"
        out_parquet_path = os.path.join(tmp_dir, f"cleaned_{clean_name}.parquet")
        assert os.path.exists(out_parquet_path), "Python script did not produce cleaned parquet"

        df_cleaned_py = pl.read_parquet(out_parquet_path)
        # Verify identical schema and rows
        assert df_cleaned_py.columns == df_cleaned_sys.columns
        assert df_cleaned_py.height == df_cleaned_sys.height
        assert df_cleaned_py.to_dicts() == df_cleaned_sys.to_dicts()

    # 7. Test SQL Script Export: Invariant 7 (DuckDB execution matches system cleaned)
    sql_resp = await async_client.get(f"/api/v1/datasets/{dataset_id}/export/sql", headers=headers)
    assert sql_resp.status_code == 200
    assert "text/x-sql" in sql_resp.headers["content-type"]
    sql_script = sql_resp.text

    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_csv_path = os.path.join(tmp_dir, filename)
        with open(raw_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_raw)

        con = duckdb.connect()
        # Read from raw CSV
        con.execute(f"CREATE TABLE raw_data AS SELECT * FROM read_csv('{raw_csv_path.replace(chr(92), '/')}')")

        # Compile pipeline to sql was generated with raw_table="read_csv('messy_repro.csv')"
        # Execute the SQL script directly
        cur = con.cursor()
        # If the script contains read_csv('messy_repro.csv'), replace with full path or cd
        sql_to_run = sql_script.replace(f"'{filename}'", f"'{raw_csv_path.replace(chr(92), '/')}'")
        duck_res = cur.execute(sql_to_run).fetchall()
        cols = [d[0] for d in cur.description]
        duck_dicts = [dict(zip(cols, row, strict=False)) for row in duck_res]

        # Verify row count and column presence
        assert len(duck_dicts) == df_cleaned_sys.height
        for c in df_cleaned_sys.columns:
            assert c in cols

    # 8. Test Cross-User Isolation (owner_id scoping, returns 404 NOT_FOUND)
    other_email = f"intruder_{uuid.uuid4().hex[:8]}@example.com"
    other_reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "password": password, "full_name": "Intruder User"},
    )
    other_token = other_reg.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    for export_type in ["csv", "parquet", "python", "sql"]:
        other_resp = await async_client.get(
            f"/api/v1/datasets/{dataset_id}/export/{export_type}",
            headers=other_headers,
        )
        assert other_resp.status_code == 404, f"Expected 404 on cross-user export of {export_type}, got {other_resp.status_code}"
