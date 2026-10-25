"""Unit test for formula-safe CSV export neutralizing spreadsheet injection (CWE-1236)."""

from __future__ import annotations

import polars as pl

from app.export.csv import export_formula_safe_csv, neutralize_formula_injection


def test_neutralize_formula_injection() -> None:
    df = pl.DataFrame({
        "username": ["=cmd|' /C calc'!A0", "+12345", "-500", "@admin", "\tsome_tab", "\rcarriage", "normal_user"],
        "age": [25, 30, 35, 40, 45, 50, 55],
        "notes": [None, "=SUM(A1:A10)", "safe note", None, "-test", "@mention", "hello"],
    })

    safe_df = neutralize_formula_injection(df)

    usernames = safe_df["username"].to_list()
    assert usernames[0] == "'=cmd|' /C calc'!A0"
    assert usernames[1] == "'+12345"
    assert usernames[2] == "'-500"
    assert usernames[3] == "'@admin"
    assert usernames[4] == "'\tsome_tab"
    assert usernames[5] == "'\rcarriage"
    assert usernames[6] == "normal_user"

    notes = safe_df["notes"].to_list()
    assert notes[0] is None
    assert notes[1] == "'=SUM(A1:A10)"
    assert notes[2] == "safe note"
    assert notes[3] is None
    assert notes[4] == "'-test"
    assert notes[5] == "'@mention"
    assert notes[6] == "hello"


def test_export_formula_safe_csv_bytes() -> None:
    df = pl.DataFrame({
        "formula": ["=2+2", "plain text"],
        "value": [10, 20],
    })
    csv_bytes = export_formula_safe_csv(df)
    csv_str = csv_bytes.decode("utf-8")
    assert "'=2+2" in csv_str
    assert "plain text" in csv_str
