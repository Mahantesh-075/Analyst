"""JSON serialization utilities ensuring PostgreSQL JSONB compatibility."""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, time
from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize complex Python/Polars/Numpy types into JSON-serializable primitives."""
    if obj is None:
        return None
    if isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return sanitize_for_json(obj.item())
        except Exception:
            pass
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        try:
            return sanitize_for_json(obj.to_dict())
        except Exception:
            pass
    return str(obj)
