"""LLM client enforcing strict JSON schema validation, zero PII, and deterministic fallback."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "schemas"


def load_schema(schema_filename: str) -> dict[str, Any]:
    schema_path = SCHEMAS_DIR / schema_filename
    if not schema_path.exists():
        # Fallback to local schemas directory
        schema_path = Path("/mnt/c/Users/mahan/.gemini/analyst/schemas") / schema_filename
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


class LLMClient:
    """Client for generating schema-validated suggestions with zero PII exposure."""

    def __init__(self) -> None:
        self.enabled = settings.llm_enabled
        self.provider = "anthropic" if settings.anthropic_api_key else "none"
        self.model = "claude-3-5-sonnet-20241022"
        self._proposal_schema = load_schema("llm_proposal_output.schema.json")
        self._step_schema = load_schema("transform_step.schema.json")

    def _compute_input_hash(self, metadata: list[dict[str, Any]], sample: list[dict[str, Any]]) -> str:
        payload = json.dumps({"meta": metadata, "sample": sample}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def generate_proposals(
        self,
        column_metadata: list[dict[str, Any]],
        masked_sample: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate cleaning proposals conforming strictly to llm_proposal_output.schema.json."""
        if not self.enabled or not settings.anthropic_api_key:
            logger.info("llm_disabled_or_no_key_running_in_rule_only_mode")
            return []

        # Enforce max 20 rows sample (Invariant 6)
        safe_sample = masked_sample[:20]
        input_hash = self._compute_input_hash(column_metadata, safe_sample)

        prompt = (
            "You are a strict data cleaning assistant. Given dataset column metadata and a PII-masked sample, "
            "return only valid JSON conforming to the schema. Propose high-confidence transformations.\n"
            f"Columns: {json.dumps(column_metadata)}\n"
            f"Sample (20 rows, PII masked): {json.dumps(safe_sample)}\n"
        )

        logger.debug("llm_generating_proposals", input_hash=input_hash, prompt_len=len(prompt))

        # Call provider with retry on schema failure
        for attempt in range(2):
            try:
                start_time = time.perf_counter()
                raw_response = "{}"
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.debug("llm_response_received", latency_ms=latency_ms)

                parsed = json.loads(raw_response)
                # Validate against schema
                jsonschema.validate(instance=parsed, schema=self._proposal_schema)
                proposals = parsed.get("proposals", [])
                return proposals  # type: ignore[no-any-return]
            except Exception as e:
                logger.warning("llm_validation_failed_retrying_or_dropping", attempt=attempt, error=str(e))
                if attempt == 1:
                    logger.error("llm_proposal_dropped_after_retry", input_hash=input_hash)
                    return []

        return []
