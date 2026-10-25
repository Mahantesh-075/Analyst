"""Closed registry for all data transformation operations."""

from __future__ import annotations

from typing import Any

from app.ops.base import BaseOp
from app.ops.cast_type import CastTypeOp
from app.ops.drop_column import DropColumnOp
from app.ops.drop_duplicates import DropDuplicatesOp
from app.ops.drop_null_rows import DropNullRowsOp
from app.ops.handle_outliers import HandleOutliersOp
from app.ops.impute import ImputeOp
from app.ops.map_values import MapValuesOp
from app.ops.mask_pii import MaskPiiOp
from app.ops.normalize_case import NormalizeCaseOp
from app.ops.parse_date import ParseDateOp
from app.ops.rename_column import RenameColumnOp
from app.ops.split_column import SplitColumnOp
from app.ops.standardize_missing import StandardizeMissingOp
from app.ops.trim_whitespace import TrimWhitespaceOp

OP_REGISTRY: dict[str, type[BaseOp]] = {
    RenameColumnOp.name: RenameColumnOp,
    CastTypeOp.name: CastTypeOp,
    TrimWhitespaceOp.name: TrimWhitespaceOp,
    NormalizeCaseOp.name: NormalizeCaseOp,
    StandardizeMissingOp.name: StandardizeMissingOp,
    ImputeOp.name: ImputeOp,
    DropNullRowsOp.name: DropNullRowsOp,
    DropDuplicatesOp.name: DropDuplicatesOp,
    ParseDateOp.name: ParseDateOp,
    HandleOutliersOp.name: HandleOutliersOp,
    MapValuesOp.name: MapValuesOp,
    SplitColumnOp.name: SplitColumnOp,
    DropColumnOp.name: DropColumnOp,
    MaskPiiOp.name: MaskPiiOp,
}


def get_op(name: str, params: dict[str, Any]) -> BaseOp:
    """Instantiate an op from the closed registry given its name and parameter dictionary."""
    if name not in OP_REGISTRY:
        raise ValueError(f"Unknown or unregistered operation: {name!r}. Allowed: {sorted(OP_REGISTRY.keys())}")
    op_cls = OP_REGISTRY[name]
    return op_cls(**params)


def parse_transform_step(step_dict: dict[str, Any]) -> BaseOp:
    """Parse and validate a transform step dictionary conforming to schemas/transform_step.schema.json."""
    if "op" not in step_dict or "params" not in step_dict:
        raise ValueError("Invalid transform step dictionary: missing 'op' or 'params' key")
    return get_op(step_dict["op"], step_dict["params"])


def compile_pipeline_to_python(steps: list[BaseOp], raw_file_path: str, output_parquet_path: str) -> str:
    """Compile an ordered sequence of ops into a standalone, reproducible Python script."""
    lines = [
        '"""Auto-generated reproducible data cleaning pipeline by Analyst."""',
        "import polars as pl",
        "",
        "def run_pipeline() -> pl.DataFrame:",
        "    # Load raw data",
        f"    if {raw_file_path!r}.endswith('.parquet'):",
        f"        df = pl.read_parquet({raw_file_path!r})",
        "    else:",
        f"        df = pl.read_csv({raw_file_path!r})",
        "",
    ]

    for i, step in enumerate(steps, 1):
        lines.append(f"    # Step {i}: {step.name}")
        py_code = step.to_python("df")
        for code_line in py_code.splitlines():
            lines.append(f"    {code_line}")
        lines.append("")

    lines.extend([
        "    # Save cleaned result",
        f"    df.write_parquet({output_parquet_path!r})",
        f"    print('Pipeline executed successfully. Cleaned dataset saved to: {output_parquet_path}')",
        "    return df",
        "",
        'if __name__ == "__main__":',
        "    run_pipeline()",
        "",
    ])

    return "\n".join(lines)


def compile_pipeline_to_sql(steps: list[BaseOp], raw_table: str = "raw_data") -> str:
    """Compile an ordered sequence of ops into a DuckDB SQL script with Common Table Expressions (CTEs)."""
    if not steps:
        return f"SELECT * FROM {raw_table};"

    cte_lines: list[str] = []
    current_table = raw_table

    for i, step in enumerate(steps, 1):
        next_table = f"step_{i}"
        sql_cte = step.to_sql(current_table, next_table)
        cte_lines.append(sql_cte)
        current_table = next_table

    combined_ctes = ",\n".join(cte_lines)
    return f"WITH\n{combined_ctes}\nSELECT * FROM {current_table};"
