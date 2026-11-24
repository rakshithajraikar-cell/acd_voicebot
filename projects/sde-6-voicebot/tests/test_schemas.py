"""
Unit Tests for Context and Reasoning Schemas
Workstream W3 — Student: Prathibhashree K
"""

import unittest
import uuid
import sys
from pathlib import Path

# Setup module search paths
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from contracts.envelope import EventEnvelope, ErrorEnvelope, SessionState, WorkflowState
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
    ProviderStatus,
)


class TestSchemas(unittest.TestCase):
    """Verifies schema definitions, field defaults, immutability, and serialization."""

    def test_bounding_box_creation_and_dict(self):
        bb = BoundingBox(x=10, y=20, width=100, height=200, label="grades_table", confidence=0.95)
        self.assertEqual(bb.x, 10)
        self.assertEqual(bb.y, 20)
        self.assertEqual(bb.width, 100)
        self.assertEqual(bb.height, 200)
        self.assertEqual(bb.label, "grades_table")
        self.assertEqual(bb.confidence, 0.95)

        d = bb.to_dict()
        bb2 = BoundingBox.from_dict(d)
        self.assertEqual(bb, bb2)

    def test_source_reference_defaults_and_serialization(self):
        src = SourceReference(
            source_id="src_001",
            source_type=SourceType.SYNTHETIC_SCREEN,
            uri="synthetic://screen/frame_001",
            title="Student Portal",
            snippet="CS101: Grade A",
        )
        self.assertEqual(src.source_id, "src_001")
        self.assertEqual(src.source_type, SourceType.SYNTHETIC_SCREEN)
        self.assertIsNotNone(src.timestamp)

        d = src.to_dict()
        src2 = SourceReference.from_dict(d)
        self.assertEqual(src.source_id, src2.source_id)
        self.assertEqual(src.source_type, src2.source_type)
        self.assertEqual(src.uri, src2.uri)

    def test_screen_context_defaults(self):
        """NON-NEGOTIABLE RULE: Screen capture MUST default to disabled."""
        sc = ScreenContext(
            context_id=str(uuid.uuid4()),
            session_id="sess_123",
            timestamp="2026-10-31T12:00:00Z",
        )
        self.assertFalse(sc.capture_enabled, "capture_enabled MUST default to False")
        self.assertFalse(sc.capture_allowed_by_user, "capture_allowed_by_user MUST default to False")
        self.assertTrue(sc.is_synthetic, "is_synthetic MUST default to True")
        self.assertEqual(sc.screen_width, 1920)
        self.assertEqual(sc.screen_height, 1080)

        # Immutability check
        with self.assertRaises(Exception):
            sc.capture_enabled = True  # Frozen dataclass check

    def test_context_item_serialization(self):
        src = SourceReference(source_id="s1", source_type=SourceType.MOCK_DOCUMENT)
        item = ContextItem(
            item_id="item_01",
            item_type=ContextItemType.OCR_TEXT,
            content="Sample OCR content",
            source=src,
            confidence=0.99,
        )
        self.assertTrue(item.is_synthetic)
        self.assertEqual(item.ttl_seconds, 300)

        d = item.to_dict()
        item2 = ContextItem.from_dict(d)
        self.assertEqual(item.item_id, item2.item_id)
        self.assertEqual(item.content, item2.content)
        self.assertEqual(item.source.source_id, item2.source.source_id)

    def test_reasoning_request_defaults(self):
        req = ReasoningRequest.create(
            session_id="sess_abc",
            correlation_id="corr_xyz",
            user_query="What is my CS101 grade?",
        )
        self.assertTrue(req.mock_mode, "mock_mode must default to True")
        self.assertEqual(req.temperature, 0.0, "temperature must default to 0.0 for deterministic execution")
        self.assertEqual(req.max_tokens, 1024)
        self.assertEqual(req.prompt_version, "1.0.0")

        d = req.to_dict()
        req2 = ReasoningRequest.from_dict(d)
        self.assertEqual(req.user_query, req2.user_query)
        self.assertEqual(req.session_id, req2.session_id)

    def test_reasoning_result_serialization(self):
        src = SourceReference(source_id="src_99", source_type=SourceType.SYNTHETIC_SCREEN)
        res = ReasoningResult(
            result_id="res_01",
            request_id="req_01",
            session_id="sess_01",
            correlation_id="corr_01",
            response_text="Grounded answer text",
            sources_used=[src],
            confidence=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            has_sufficient_evidence=True,
            execution_time_ms=12.5,
            is_mock=True,
        )
        self.assertTrue(res.is_mock)
        d = res.to_dict()
        res2 = ReasoningResult.from_dict(d)
        self.assertEqual(res.result_id, res2.result_id)
        self.assertEqual(res.confidence_level, res2.confidence_level)
        self.assertEqual(len(res2.sources_used), 1)

    def test_event_and_error_envelopes(self):
        evt = EventEnvelope.create(
            event_type="reasoning.completed",
            session_id="s1",
            correlation_id="c1",
            producer="w3.reasoning",
            payload={"key": "val"},
        )
        self.assertEqual(evt.producer, "w3.reasoning")
        self.assertEqual(evt.schema_version, "1.0.0")

        err = ErrorEnvelope(
            code="INSUFFICIENT_EVIDENCE",
            message_safe_for_user="Context lacked sufficient evidence",
            retryable=False,
            correlation_id="c1",
        )
        self.assertEqual(err.code, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(err.retryable)

        # Enums
        self.assertEqual(SessionState.ACTIVE.value, "active")
        self.assertEqual(WorkflowState.AWAITING_APPROVAL.value, "awaiting_approval")
        self.assertEqual(ProviderStatus.HEALTHY.value, "healthy")


if __name__ == "__main__":
    unittest.main()
