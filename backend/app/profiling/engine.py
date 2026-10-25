import math
import re
from typing import Any

import polars as pl

from app.profiling.pii import detect_column_pii, mask_value

MISSING_CANDIDATE_TOKENS = {
    "n/a",
    "na",
    "null",
    "none",
    "-",
    "--",
    "?",
    "nil",
    "undefined",
    "missing",
    "",
}

DATE_PATTERN = re.compile(r"^\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}$")


class ProfilingEngine:
    def detect_missing_tokens(self, series: pl.Series) -> list[str]:
        """Detect distinct placeholder missing tokens stored as text in a series."""
        if series.dtype != pl.Utf8:
            return []

        tokens: set[str] = set()
        # Take sample of string values
        sample = series.drop_nulls().head(5000).to_list()
        for val in sample:
            if isinstance(val, str):
                cleaned = val.strip().lower()
                if cleaned in MISSING_CANDIDATE_TOKENS:
                    tokens.add(val.strip())
        return sorted(tokens)

    def analyze_dates(self, series: pl.Series) -> dict[str, Any]:
        """Check for date patterns and day-first vs month-first ambiguity."""
        if series.dtype not in [pl.Utf8, pl.Date, pl.Datetime]:
            return {"is_date": False, "is_ambiguous": False}

        if series.dtype in [pl.Date, pl.Datetime]:
            return {"is_date": True, "is_ambiguous": False, "format": "iso"}

        sample = series.drop_nulls().head(500).to_list()
        str_dates = [s for s in sample if isinstance(s, str) and DATE_PATTERN.match(s.strip())]
        if len(str_dates) < max(5, int(0.3 * len(sample)) if sample else 1):
            return {"is_date": False, "is_ambiguous": False}

        # Check day-first vs month-first ambiguity (e.g. 05/06/2023)
        ambiguous_count = 0
        for d in str_dates:
            parts = re.split(r"[-/\.]", d.strip())
            if len(parts) == 3:
                try:
                    p1, p2 = int(parts[0]), int(parts[1])
                    if 1 <= p1 <= 12 and 1 <= p2 <= 12 and p1 != p2:
                        ambiguous_count += 1
                except ValueError:
                    pass

        is_ambiguous = ambiguous_count > 0 and (ambiguous_count / len(str_dates)) > 0.5
        return {
            "is_date": True,
            "is_ambiguous": is_ambiguous,
            "sample_format": "ambiguous (DD/MM vs MM/DD)" if is_ambiguous else "inferred",
        }

    def compute_column_profile(self, series: pl.Series, position: int) -> dict[str, Any]:
        """Deterministic computation of column statistics via Polars."""
        total_rows = len(series)
        null_count = series.null_count()
        null_pct = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

        non_null_series = series.drop_nulls()
        distinct_count = non_null_series.n_unique()

        dtype_str = str(series.dtype)
        is_numeric = series.dtype in [
            pl.Int8, pl.Int16, pl.Int32, pl.Int64,
            pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
            pl.Float32, pl.Float64,
        ]

        stats: dict[str, Any] = {}
        missing_tokens = self.detect_missing_tokens(series)
        date_info = self.analyze_dates(series)

        # Top 10 most frequent values
        value_counts = (
            non_null_series.value_counts()
            .sort("count", descending=True)
            .head(10)
        )
        top_k = [
            {"value": str(row[0]), "count": int(row[1])}
            for row in value_counts.iter_rows()
        ]

        if is_numeric and len(non_null_series) > 0:
            c_min = float(non_null_series.min())  # type: ignore[arg-type]
            c_max = float(non_null_series.max())  # type: ignore[arg-type]
            c_mean = float(non_null_series.mean())  # type: ignore[arg-type]
            c_median = float(non_null_series.median())  # type: ignore[arg-type]
            std_raw = non_null_series.std()
            c_std = float(std_raw) if isinstance(std_raw, (int, float)) else 0.0

            # Quantiles
            q25 = float(non_null_series.quantile(0.25))  # type: ignore[arg-type]
            q75 = float(non_null_series.quantile(0.75))  # type: ignore[arg-type]
            iqr = q75 - q25
            lower_iqr = q25 - 1.5 * iqr
            upper_iqr = q75 + 1.5 * iqr

            outliers_count = non_null_series.filter(
                (non_null_series < lower_iqr) | (non_null_series > upper_iqr)
            ).len()

            stats = {
                "min": c_min if not math.isnan(c_min) else None,
                "max": c_max if not math.isnan(c_max) else None,
                "mean": round(c_mean, 4) if not math.isnan(c_mean) else None,
                "median": round(c_median, 4) if not math.isnan(c_median) else None,
                "std": round(c_std, 4) if not math.isnan(c_std) else None,
                "q25": round(q25, 4),
                "q75": round(q75, 4),
                "iqr": round(iqr, 4),
                "outliers_count": outliers_count,
            }
        elif series.dtype == pl.Utf8 and len(non_null_series) > 0:
            lengths = non_null_series.str.len_bytes()
            stats = {
                "min_length": int(lengths.min()),  # type: ignore[arg-type]
                "max_length": int(lengths.max()),  # type: ignore[arg-type]
                "avg_length": round(float(lengths.mean()), 2),  # type: ignore[arg-type]
            }

        stats["top_k"] = top_k
        stats["date_info"] = date_info

        # Deterministic PII detection
        sample_vals = non_null_series.head(500).to_list()
        is_pii, pii_types, pii_confidence = detect_column_pii(series.name, sample_vals)

        return {
            "position": position,
            "name": series.name,
            "inferred_dtype": dtype_str,
            "null_count": null_count,
            "null_pct": null_pct,
            "distinct_count": distinct_count,
            "missing_tokens": missing_tokens,
            "stats": stats,
            "is_pii": is_pii,
            "pii_types": pii_types,
            "semantic_confidence": pii_confidence if is_pii else None,
            "semantic_type": pii_types[0] if pii_types else ("date" if date_info["is_date"] else None),
        }

    def profile_dataframe(self, df: pl.DataFrame) -> dict[str, Any]:
        """Compute full dataset profile and per-column profiles."""
        total_rows = df.height
        total_cols = df.width

        # Check exact duplicate rows (excluding __row_idx if present)
        feature_cols = [c for c in df.columns if c != "__row_idx"]
        duplicate_rows_count = df.select(feature_cols).is_duplicated().sum() if total_rows > 0 else 0

        columns_profile = []
        constant_columns = []
        id_columns = []

        for i, col_name in enumerate(df.columns):
            col_prof = self.compute_column_profile(df[col_name], i)
            columns_profile.append(col_prof)

            if col_prof["distinct_count"] == 1:
                constant_columns.append(col_name)
            if col_prof["distinct_count"] == total_rows and total_rows > 1:
                id_columns.append(col_name)

        summary = {
            "total_rows": total_rows,
            "total_cols": total_cols,
            "duplicate_rows_count": int(duplicate_rows_count),
            "constant_columns": constant_columns,
            "id_columns": id_columns,
            "has_pii": any(c["is_pii"] for c in columns_profile),
        }

        return {
            "summary": summary,
            "columns": columns_profile,
        }

    def generate_masked_sample(
        self,
        df: pl.DataFrame,
        columns_profile: list[dict[str, Any]],
        n_rows: int = 20,
    ) -> list[dict[str, Any]]:
        """Generate a strictly PII-masked sample for LLM proposals."""
        sample_df = df.head(n_rows)
        pii_map = {c["name"]: c["pii_types"] for c in columns_profile if c["is_pii"]}

        rows = []
        for row_dict in sample_df.to_dicts():
            masked_row = {}
            for col, val in row_dict.items():
                if col in pii_map:
                    masked_row[col] = mask_value(val, pii_map[col])
                else:
                    masked_row[col] = val
            rows.append(masked_row)
        return rows
