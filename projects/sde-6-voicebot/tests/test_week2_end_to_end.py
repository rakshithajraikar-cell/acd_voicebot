"""
End-to-End Integration Tests for Week 2 Pipeline
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Verifies complete integrated pipeline:
1. Opt-in ScreenCaptureAdapter (off by default, opt-in consent, sampling and size limits).
2. MockVisionOCRAdapter (structured OCR extraction from synthetic frame).
3. BoundedContextBuilder (bounded token budget, stale filtering, relevance/recency ranking).
4. LLMClientAdapter (mock by default, timeout protection, bounded retry, validated structured output).
"""

import datetime
import unittest
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from contracts.context import (
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
)
from contracts.reasoning import (
    ReasoningRequest,
    ReasoningResult,
    ConfidenceLevel,
)
from src.voicebot.context.capture_adapter import ScreenCaptureAdapter, CaptureState
from src.voicebot.context.synthetic_frames import SyntheticFixture
from src.voicebot.context.vision_adapter import MockVisionOCRAdapter
from src.voicebot.context.context_builder import BoundedContextBuilder
from src.voicebot.reasoning.llm_adapter import LLMClientAdapter


class TestWeek2PipelineEndToEnd(unittest.TestCase):

    def setUp(self):
        self.session_id = "test-session-e2e-w2"
        self.correlation_id = "corr-e2e-w2"

        # Initialize all Week 2 components with mock defaults
        self.capture_adapter = ScreenCaptureAdapter(
            session_id=self.session_id,
            min_interval_seconds=0.1,
            max_width=1920,
            max_height=1080,
        )
        self.vision_adapter = MockVisionOCRAdapter(mock_mode=True, simulated_latency_ms=0.0)
        self.context_builder = BoundedContextBuilder(
            default_token_budget=512,
            default_ttl_seconds=300,
            relevance_weight=0.7,
            recency_weight=0.3,
        )
        self.llm_adapter = LLMClientAdapter(
            mock_mode=True,
            timeout_seconds=2.0,
            max_retries=2,
        )

    def test_full_opt_in_to_grounded_llm_response_flow(self):
        """
        Tests complete journey:
        Step 1: User explicitly opts in to screen context capture.
        Step 2: Capture adapter produces synthetic frame respecting size limits.
        Step 3: Vision adapter extracts structured text and bounding boxes.
        Step 4: Context builder packs relevant context items within token budget.
        Step 5: LLM adapter produces schema-validated ReasoningResult grounded in evidence.
        """
        # 1. Privacy gate: initially OFF
        self.assertFalse(self.capture_adapter.is_enabled)
        state = self.capture_adapter.grant_consent_and_enable()
        self.assertEqual(state, CaptureState.ACTIVE)

        # 2. Capture synthetic frame
        self.capture_adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)
        frame = self.capture_adapter.capture_frame()
        self.assertTrue(frame.capture_enabled)
        self.assertTrue(frame.is_synthetic)

        # 3. Vision / OCR extraction
        ocr_result = self.vision_adapter.process_frame(frame)
        self.assertIn("CS101", ocr_result.text)
        self.assertGreater(len(ocr_result.bounding_boxes), 0)

        # 4. Context item construction & Bounded Context Builder ingestion
        source_ref = SourceReference(
            source_id="src-frame-001",
            source_type=SourceType.SYNTHETIC_SCREEN,
            uri="synthetic://screen/frame_grades_001",
            title=frame.window_title,
            snippet=ocr_result.text[:120],
        )
        item = ContextItem(
            item_id="item-grades-001",
            item_type=ContextItemType.OCR_TEXT,
            content=ocr_result.text,
            source=source_ref,
            confidence=ocr_result.confidence,
            ttl_seconds=300,
            is_synthetic=True,
        )
        self.context_builder.add_item(item)

        # Build context for user query
        user_query = "What grade did I receive in CS101 and what is my GPA?"
        context_result = self.context_builder.build_context(query=user_query, token_budget=512)

        self.assertGreater(len(context_result.selected_items), 0)
        self.assertLessEqual(context_result.total_tokens, 512)
        self.assertIn("CS101", context_result.formatted_context)

        # 5. LLM Client Adapter reasoning
        request = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query=user_query,
            context_items=context_result.selected_items,
            prompt_version="1.0.0",
        )

        response = self.llm_adapter.generate(request)

        # Verify final ReasoningResult schema validation
        self.assertIsInstance(response, ReasoningResult)
        self.assertTrue(response.is_mock)
        self.assertEqual(response.session_id, self.session_id)
        self.assertEqual(response.correlation_id, self.correlation_id)
        self.assertTrue(response.has_sufficient_evidence)
        self.assertIn("CS101", response.response_text)
        self.assertGreater(len(response.sources_used), 0)
        self.assertEqual(response.confidence_level, ConfidenceLevel.HIGH)

    def test_revocation_clears_context_and_produces_uncertainty(self):
        """
        When user withdraws consent, screen context is purged and LLM surfaces uncertainty.
        """
        # User opts in, then withdraws
        self.capture_adapter.grant_consent_and_enable()
        self.capture_adapter.withdraw_consent()
        self.assertFalse(self.capture_adapter.is_enabled)

        # Frame captured after revocation is empty
        frame = self.capture_adapter.capture_frame()
        self.assertFalse(frame.capture_enabled)
        ocr_result = self.vision_adapter.process_frame(frame)
        self.assertEqual(ocr_result.text, "")

        # Reasoning without context items
        request = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="What are my grades?",
            context_items=[],
        )
        response = self.llm_adapter.generate(request)

        self.assertFalse(response.has_sufficient_evidence)
        self.assertIsNotNone(response.uncertainty_reason)
        self.assertEqual(response.confidence_level, ConfidenceLevel.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
