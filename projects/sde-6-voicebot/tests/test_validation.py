"""
Unit Tests for Request and Result Validation
Workstream W3 — Student: Prathibhashree K
"""

import unittest
import uuid
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from contracts.envelope import ErrorEnvelope
from contracts.context import (
    ScreenContext,
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
    BoundingBox,
)
from contracts.reasoning import (
    ReasoningRequest,
    ReasoningResult,
    ConfidenceLevel,
)
from src.voicebot.validation.validators import (
    ValidationError,
    validate_bounding_box,
    validate_source_reference,
    validate_context_item,
    validate_screen_context,
    validate_reasoning_request,
    validate_reasoning_result,
    format_error_envelope,
)


class TestValidation(unittest.TestCase):
    """
    Verifies input/output validation for normal, boundary, and error scenarios.
    """

    def test_valid_request_passes(self):
        req = ReasoningRequest.create(
            session_id="sess_ok",
            correlation_id="corr_ok",
            user_query="Valid query string",
        )
        validated = validate_reasoning_request(req)
        self.assertEqual(validated.user_query, "Valid query string")

    def test_invalid_request_empty_query(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_reasoning_request({
                "request_id": str(uuid.uuid4()),
                "session_id": "sess_1",
                "correlation_id": "corr_1",
                "user_query": "   ",  # Empty / whitespace only
            })
        self.assertEqual(ctx.exception.field_name, "user_query")
        self.assertEqual(ctx.exception.code, "EMPTY_FIELD")

    def test_invalid_request_temperature_out_of_range(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_reasoning_request({
                "request_id": str(uuid.uuid4()),
                "session_id": "sess_1",
                "correlation_id": "corr_1",
                "user_query": "Query",
                "temperature": 1.5,  # > 1.0
            })
        self.assertEqual(ctx.exception.field_name, "temperature")
        self.assertEqual(ctx.exception.code, "OUT_OF_RANGE")

    def test_invalid_request_max_tokens_zero_or_negative(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_reasoning_request({
                "request_id": str(uuid.uuid4()),
                "session_id": "sess_1",
                "correlation_id": "corr_1",
                "user_query": "Query",
                "max_tokens": 0,
            })
        self.assertEqual(ctx.exception.field_name, "max_tokens")
        self.assertEqual(ctx.exception.code, "OUT_OF_BOUNDS")

    def test_bounding_box_validation(self):
        # Negative x
        with self.assertRaises(ValidationError):
            validate_bounding_box(BoundingBox(x=-1, y=0, width=10, height=10, label="box"))
        # Zero width
        with self.assertRaises(ValidationError):
            validate_bounding_box(BoundingBox(x=0, y=0, width=0, height=10, label="box"))
        # Empty label
        with self.assertRaises(ValidationError):
            validate_bounding_box(BoundingBox(x=0, y=0, width=10, height=10, label=""))
        # Confidence out of range
        with self.assertRaises(ValidationError):
            validate_bounding_box(BoundingBox(x=0, y=0, width=10, height=10, label="box", confidence=1.2))

    def test_privacy_non_synthetic_rejected(self):
        """Rejects any context item or screen context marked as non-synthetic."""
        src = SourceReference(source_id="src_1", source_type=SourceType.USER_PROMPT)
        with self.assertRaises(ValidationError) as ctx:
            validate_context_item(ContextItem(
                item_id="ci_1",
                item_type=ContextItemType.USER_SELECTION,
                content="Real user data",
                source=src,
                is_synthetic=False,  # Forbidden!
            ))
        self.assertEqual(ctx.exception.code, "PRIVACY_VIOLATION")

    def test_reasoning_result_uncertainty_requirement(self):
        """When has_sufficient_evidence is False, uncertainty_reason MUST be provided."""
        res = ReasoningResult(
            result_id="res_01",
            request_id="req_01",
            session_id="sess_01",
            correlation_id="corr_01",
            response_text="I don't know",
            has_sufficient_evidence=False,
            uncertainty_reason=None,  # Missing!
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_reasoning_result(res)
        self.assertEqual(ctx.exception.field_name, "uncertainty_reason")

    def test_format_error_envelope_conversion(self):
        """Verifies clear error mapping to standard ErrorEnvelope."""
        val_err = ValidationError("Value too large", "screen_width", "OUT_OF_BOUNDS")
        env = format_error_envelope(val_err, correlation_id="corr-err-123")

        self.assertIsInstance(env, ErrorEnvelope)
        self.assertEqual(env.code, "OUT_OF_BOUNDS")
        self.assertEqual(env.correlation_id, "corr-err-123")
        self.assertFalse(env.retryable)
        self.assertIn("screen_width", env.message_safe_for_user)
        self.assertEqual(env.details_redacted["field"], "screen_width")


if __name__ == "__main__":
    unittest.main()
