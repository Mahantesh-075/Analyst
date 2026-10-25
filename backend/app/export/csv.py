"""Formula-safe CSV exporter neutralizing CSV injection (CWE-1236)."""

from __future__ import annotations

import io

import polars as pl

# Characters that trigger formula execution in spreadsheet software (Excel, LibreOffice, Google Sheets)
INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize_formula_injection(df: pl.DataFrame) -> pl.DataFrame:
    """Neutralize formula injection by prefixing hostile characters with a single quote."""
    exprs: list[pl.Expr] = []
    for col in df.columns:
        dtype = df[col].dtype
        if dtype in (pl.String, pl.Utf8):
            cond: pl.Expr | None = None
            for pfx in INJECTION_PREFIXES:
                pfx_cond = pl.col(col).str.starts_with(pfx)
                cond = pfx_cond if cond is None else (cond | pfx_cond)

            if cond is not None:
                exprs.append(
                    pl.when(cond.fill_null(False))
                    .then(pl.concat_str([pl.lit("'"), pl.col(col)]))
                    .otherwise(pl.col(col))
                    .alias(col)
                )
            else:
                exprs.append(pl.col(col))
        else:
            exprs.append(pl.col(col))

    return df.with_columns(exprs)


def export_formula_safe_csv(df: pl.DataFrame) -> bytes:
    """Export Polars DataFrame to CSV bytes with formula injection neutralization."""
    safe_df = neutralize_formula_injection(df)
    buf = io.BytesIO()
    safe_df.write_csv(buf)
    return buf.getvalue()
