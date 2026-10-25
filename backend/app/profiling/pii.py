import re
from typing import Any

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9]{1,4}?[-.\s]?\(?[0-9]{2,5}?\)?[-.\s]?[0-9]{3,5}[-.\s]?[0-9]{3,5}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
AADHAAR_PATTERN = re.compile(r"^[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}$")

NAME_COLUMN_KEYWORDS = {
    "name",
    "firstname",
    "first_name",
    "lastname",
    "last_name",
    "fullname",
    "full_name",
    "customer_name",
    "beneficiary",
    "donor",
    "patient",
    "employee_name",
}


def detect_cell_pii(val: Any) -> list[str]:
    """Check a single cell against deterministic PII patterns."""
    if val is None or not isinstance(val, str):
        return []

    text = val.strip()
    if not text:
        return []

    types = []
    if EMAIL_PATTERN.match(text):
        types.append("email")
    if PHONE_PATTERN.match(text) and sum(c.isdigit() for c in text) >= 10:
        types.append("phone")
    if PAN_PATTERN.match(text.upper()):
        types.append("pan")
    if AADHAAR_PATTERN.match(text):
        types.append("aadhaar")

    return types


def detect_column_pii(col_name: str, values: list[Any]) -> tuple[bool, list[str], float]:
    """Detect PII across sample values of a column.

    Returns (is_pii, pii_types, confidence).
    """
    cleaned_col = re.sub(r"[^a-z0-9]", "", col_name.lower())
    col_has_name_hint = any(k in cleaned_col for k in ["name", "beneficiary", "donor", "patient"])

    str_vals = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not str_vals:
        if col_has_name_hint:
            return True, ["name"], 0.8
        return False, [], 0.0

    type_counts: dict[str, int] = {"email": 0, "phone": 0, "pan": 0, "aadhaar": 0}
    for v in str_vals:
        for t in detect_cell_pii(v):
            type_counts[t] += 1

    total = len(str_vals)
    detected_types = []
    highest_ratio = 0.0

    for pii_type, count in type_counts.items():
        ratio = count / total
        if ratio >= 0.2:  # at least 20% match in column sample
            detected_types.append(pii_type)
            if ratio > highest_ratio:
                highest_ratio = ratio

    if col_has_name_hint:
        detected_types.append("name")
        highest_ratio = max(highest_ratio, 0.85)

    is_pii = len(detected_types) > 0
    confidence = min(1.0, highest_ratio if is_pii else 0.0)
    return is_pii, detected_types, round(confidence, 2)


def mask_value(val: Any, pii_types: list[str]) -> Any:
    """Mask PII in a cell before exposing to LLMs or non-secure views."""
    if val is None or not isinstance(val, str):
        return val

    s = val.strip()
    if not s:
        return val

    if "email" in pii_types:
        parts = s.split("@")
        if len(parts) == 2:
            return f"{parts[0][:1]}***@{parts[1]}"
        return "[EMAIL_MASKED]"

    if "phone" in pii_types:
        digits = re.sub(r"\D", "", s)
        if len(digits) >= 4:
            return f"***-***-{digits[-4:]}"
        return "[PHONE_MASKED]"

    if "pan" in pii_types:
        if len(s) == 10:
            return f"{s[:2]}***{s[-2:]}"
        return "[PAN_MASKED]"

    if "aadhaar" in pii_types:
        clean = re.sub(r"\s", "", s)
        if len(clean) >= 4:
            return f"XXXX-XXXX-{clean[-4:]}"
        return "[AADHAAR_MASKED]"

    if "name" in pii_types:
        tokens = s.split()
        return " ".join(f"{t[:1]}***" for t in tokens) or "[NAME_MASKED]"

    return s
