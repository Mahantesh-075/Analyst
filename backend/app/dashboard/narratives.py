"""Deterministic narrative validation and formatting adhering strictly to Invariant 3.

Invariant 3:
All Displayed Numbers Are Deterministically Computed: Polars and DuckDB compute every metric,
quantile, outlier, KPI, and preview. LLM narrative generation uses strict placeholders
(e.g. {{kpi_id}}) bound to computed values. Any digit in a narrative template outside
a placeholder causes immediate rejection.
"""

from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]{0,40})\}\}")
DIGIT_RE = re.compile(r"\d")


class InvariantViolationError(ValueError):
    """Raised when an architectural invariant is violated."""


def validate_narrative_template(template: str, allowed_refs: set[str]) -> list[str]:
    """Validate a narrative template against Invariant 3.

    1. All placeholders must match {{ref_id}} and be in allowed_refs.
    2. Any digit outside of {{ref_id}} placeholders triggers immediate rejection.
    Returns list of extracted ref IDs.
    """
    if len(template) > 300:
        raise InvariantViolationError("Narrative template exceeds maximum length of 300 characters.")

    # 1. Extract placeholders
    refs_found: list[str] = []
    for match in PLACEHOLDER_RE.finditer(template):
        ref_id = match.group(1)
        if ref_id not in allowed_refs:
            raise InvariantViolationError(
                f"Narrative references unknown KPI/ref: '{ref_id}'. Allowed refs: {sorted(allowed_refs)}"
            )
        refs_found.append(ref_id)

    # 2. Check for digits outside placeholders
    # Replace all valid placeholders with a safe non-digit string
    stripped = PLACEHOLDER_RE.sub("", template)
    digit_match = DIGIT_RE.search(stripped)
    if digit_match:
        found_digit = digit_match.group(0)
        raise InvariantViolationError(
            f"Invariant 3 Violation: Found hardcoded digit '{found_digit}' outside placeholder in template: '{template}'. "
            "All numbers must be computed deterministically via {{placeholder}} bindings."
        )

    return refs_found


def format_kpi_value(value: Any, format_type: str = "decimal") -> str:
    """Deterministically format numeric KPI values according to format specification."""
    if value is None:
        return "N/A"

    if isinstance(value, (int, float)):
        if format_type == "integer":
            return f"{int(round(value)):,}"
        elif format_type == "percent":
            return f"{value * 100:.1f}%" if value <= 1.0 else f"{value:.1f}%"
        elif format_type == "currency":
            return f"${value:,.2f}"
        else:  # decimal
            if isinstance(value, int) or value.is_integer():
                return f"{int(value):,}"
            return f"{value:,.2f}"
    return str(value)


def render_narrative(
    template: str,
    kpi_values: dict[str, Any],
    kpi_formats: dict[str, str] | None = None,
) -> str:
    """Render a validated narrative template by binding computed values."""
    formats = kpi_formats or {}

    def replacer(match: re.Match[str]) -> str:
        ref_id = match.group(1)
        val = kpi_values.get(ref_id)
        fmt = formats.get(ref_id, "decimal")
        return format_kpi_value(val, fmt)

    return PLACEHOLDER_RE.sub(replacer, template)
