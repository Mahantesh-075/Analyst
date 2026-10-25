"""Seed demo account and realistic dataset into live running Analyst system."""

import urllib.request
import json
import uuid

BASE_URL = "http://127.0.0.1:8000/api/v1"

def main():
    print("1. Authenticating demo user (Mahant)...")
    email = "demo@analyst.com"
    password = "DemoPassword123!"
    
    login_payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=login_payload,
        headers={"Content-Type": "application/json"}
    )
    
    token = None
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            token = data["access_token"]
            print(f"Logged in existing demo user: {email}")
    except Exception:
        reg_payload = json.dumps({
            "email": email,
            "password": password,
            "display_name": "Mahant (Principal)"
        }).encode("utf-8")
        req_reg = urllib.request.Request(
            f"{BASE_URL}/auth/register",
            data=reg_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_reg) as resp:
            data = json.loads(resp.read().decode())
            token = data["access_token"]
            print(f"Registered fresh demo user: {email}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 2. Check if dataset already exists
    req_list = urllib.request.Request(f"{BASE_URL}/datasets", headers=headers)
    with urllib.request.urlopen(req_list) as resp:
        res_json = json.loads(resp.read().decode())
        existing = res_json.get("items", []) if isinstance(res_json, dict) else res_json
        if existing:
            print(f"Found {len(existing)} existing datasets for demo user:")
            for d in existing:
                print(f" - {d['name']} (ID: {d['id']}, Status: {d['status']})")

    print("2. Uploading realistic messy NGO survey dataset...")
    csv_content = (
        "beneficiary_id,name,contact_phone,age,contribution,join_date,region\n"
        "1001,  Aarav Sharma  ,+91 9876543210,34,$1,250.00,2023-01-15,North\n"
        "1002,Priya Patel,priya@example.com,N/A,$850.50,15/02/2023,West\n"
        "1003,  Aarav Sharma  ,+91 9876543210,34,$1,250.00,2023-01-15,North\n"
        "1004,Devendra Singh,,45,$3,400.00,2023-03-10,South\n"
        "1005,Ananya Gupta,9988776655,29,missing,2023-04-12,East\n"
        "1006,Kavita Rao,kavita@ngo.org,38,$2,100.00,2023-05-20,North\n"
        "1007,Rohan Verma,rohan@example.com,142,$950.00,2023-06-01,West\n"
        "1008,Sunita Joshi,sunita@domain.org,27,$1,800.00,2023-07-04,South\n"
    ).encode("utf-8")

    filename = "ngo_field_beneficiary_survey.csv"
    req_up = urllib.request.Request(
        f"{BASE_URL}/datasets/upload-url",
        data=json.dumps({"filename": filename, "file_size_bytes": len(csv_content)}).encode("utf-8"),
        headers=headers
    )
    with urllib.request.urlopen(req_up) as resp:
        up_data = json.loads(resp.read().decode())
        upload_url = up_data["upload_url"]
        s3_key = up_data["s3_key"]

    # Upload to MinIO S3
    req_s3 = urllib.request.Request(
        upload_url,
        data=csv_content,
        headers={"Content-Type": "text/csv"},
        method="PUT"
    )
    with urllib.request.urlopen(req_s3) as resp:
        print("Raw CSV stored in S3 object store.")

    # Create dataset record
    req_create = urllib.request.Request(
        f"{BASE_URL}/datasets",
        data=json.dumps({
            "name": "NGO Field Beneficiary Survey",
            "source_filename": filename,
            "s3_key": s3_key,
            "description": "Demonstration dataset with whitespace, duplicates, PII contacts, and outliers."
        }).encode("utf-8"),
        headers=headers
    )
    with urllib.request.urlopen(req_create) as resp:
        ds = json.loads(resp.read().decode())
        dataset_id = ds["id"]
        print(f"Created Dataset ID: {dataset_id}")

    print("3. Ingesting & Deterministically Profiling dataset (Invariant 1 & 3)...")
    req_ingest = urllib.request.Request(
        f"{BASE_URL}/jobs/datasets/{dataset_id}/ingest",
        data=b"{}",
        headers=headers
    )
    with urllib.request.urlopen(req_ingest) as resp:
        print("Ingestion complete. Normalized canonical Parquet saved.")

    req_prof = urllib.request.Request(
        f"{BASE_URL}/datasets/{dataset_id}/profile",
        data=b"{}",
        headers=headers
    )
    with urllib.request.urlopen(req_prof) as resp:
        print("Deterministic profile computed and saved.")

    print("4. Synthesizing Closed-Registry Cleaning Proposals (Invariant 4)...")
    req_gen = urllib.request.Request(
        f"{BASE_URL}/datasets/{dataset_id}/proposals/generate",
        data=b"{}",
        headers=headers
    )
    with urllib.request.urlopen(req_gen) as resp:
        proposals = json.loads(resp.read().decode())
        print(f"Generated {len(proposals)} proposals:")
        for p in proposals:
            print(f" - [{p['severity'].upper()}] Op: {p['op']} -> {p.get('reason', '')}")

    print("5. Accepting proposals and applying atomic cleaning plan...")
    prop_ids = [p["id"] for p in proposals]
    req_bulk = urllib.request.Request(
        f"{BASE_URL}/datasets/{dataset_id}/proposals/bulk",
        data=json.dumps({"proposal_ids": prop_ids, "status": "accepted"}).encode("utf-8"),
        headers=headers
    )
    with urllib.request.urlopen(req_bulk) as resp:
        print(f"Bulk accepted {len(prop_ids)} proposals.")

    req_apply = urllib.request.Request(
        f"{BASE_URL}/datasets/{dataset_id}/apply",
        data=b"{}",
        headers=headers
    )
    with urllib.request.urlopen(req_apply) as resp:
        apply_res = json.loads(resp.read().decode())
        print(f"Successfully applied cleaning plan! Version: {apply_res['version_number']}, Kind: {apply_res['kind']}, SHA-256: {apply_res['sha256']}")

    print("6. Verifying Dashboard metrics & Invariant 3 narrative...")
    req_dash = urllib.request.Request(
        f"{BASE_URL}/datasets/{dataset_id}/dashboard",
        headers=headers
    )
    with urllib.request.urlopen(req_dash) as resp:
        dash = json.loads(resp.read().decode())
        print(f"Computed {len(dash.get('kpis', []))} KPIs and {len(dash.get('charts', []))} Vega-Lite charts.")
        for narrative in dash.get("narratives", []):
            print(f" Executive Narrative: \"{narrative}\"")

    print("\nDEMO SEEDING COMPLETED SUCCESSFULLY! All invariants active.")

if __name__ == "__main__":
    main()
