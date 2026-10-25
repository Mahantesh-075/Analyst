import polars as pl

from app.profiling.engine import ProfilingEngine
from app.profiling.pii import detect_column_pii, mask_value


def test_pii_detection_and_masking() -> None:
    # 1. Email detection & masking
    emails = ["alice@example.com", "bob.smith@corp.org", "carol@ngo.in"]
    is_pii, pii_types, conf = detect_column_pii("email_address", emails)
    assert is_pii is True
    assert "email" in pii_types
    assert conf >= 0.8
    masked = mask_value("test.user@domain.com", ["email"])
    assert masked == "t***@domain.com"

    # 2. Phone detection & masking
    phones = ["+91-9876543210", "+1-555-123-4567", "9876543210"]
    is_pii, pii_types, _ = detect_column_pii("contact_phone", phones)
    assert is_pii is True
    assert "phone" in pii_types
    masked_phone = mask_value("+91-9876543210", ["phone"])
    assert masked_phone.endswith("3210")
    assert "98765" not in masked_phone

    # 3. PAN detection & masking
    pans = ["ABCDE1234F", "XYZPK9876Q"]
    is_pii, pii_types, _ = detect_column_pii("tax_identifier", pans)
    assert is_pii is True
    assert "pan" in pii_types
    masked_pan = mask_value("ABCDE1234F", ["pan"])
    assert masked_pan == "AB***4F"

    # 4. Non-PII column
    amounts = ["19.99", "45.00", "120.50"]
    is_pii, pii_types, _ = detect_column_pii("amount_usd", amounts)
    assert is_pii is False
    assert len(pii_types) == 0


def test_deterministic_profiling_stats() -> None:
    engine = ProfilingEngine()
    df = pl.DataFrame({
        "customer_id": [1, 2, 3, 4, 5],
        "customer_name": ["Alice Smith", "Bob Jones", "Carol White", "David Brown", "Eve Davis"],
        "email": ["alice@a.com", "bob@b.com", "carol@c.com", "david@d.com", "eve@e.com"],
        "score": [10.0, 20.0, 30.0, 40.0, 1000.0],  # 1000 is an outlier
        "status": ["active", "active", "active", "active", "active"],  # constant column
        "notes": ["N/A", "Valid note", "none", "-", "Another note"],  # missing tokens
    })

    profile = engine.profile_dataframe(df)
    summary = profile["summary"]
    assert summary["total_rows"] == 5
    assert summary["total_cols"] == 6
    assert summary["has_pii"] is True
    assert "status" in summary["constant_columns"]

    cols = {c["name"]: c for c in profile["columns"]}

    # Verify score stats and outlier detection
    score_col = cols["score"]
    assert score_col["stats"]["min"] == 10.0
    assert score_col["stats"]["max"] == 1000.0
    assert score_col["stats"]["median"] == 30.0
    assert score_col["stats"]["outliers_count"] == 1

    # Verify missing tokens in notes
    notes_col = cols["notes"]
    assert "N/A" in notes_col["missing_tokens"]
    assert "-" in notes_col["missing_tokens"]
    assert "none" in notes_col["missing_tokens"]

    # Verify masked sample has NO unmasked email or names
    sample = engine.generate_masked_sample(df, profile["columns"], n_rows=5)
    assert len(sample) == 5
    for r in sample:
        assert "@" in r["email"]
        assert "***@" in r["email"]  # masked
        assert "***" in r["customer_name"]  # masked name
