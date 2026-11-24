"""
Tests for Grounded Answers with Source References and Explicit No-Evidence Responses
SDE 6 Voicebot — Workstream W3 (Week 3 / Days 17-18)
Student: Prathibhashree K
"""

import unittest

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_root = project_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from contracts.reasoning import ReasoningRequest, ConfidenceLevel
from contracts.context import SourceType
from voicebot.context.synthetic_frames import SyntheticFixture, SyntheticFrameGenerator
from voicebot.context.observation_adapter import ObservationProducer
from voicebot.context.capture_adapter import ScreenCaptureAdapter
from voicebot.reasoning.mock_reasoner import MockReasoningEngine


class TestGroundedAnswersAndNoEvidence(unittest.TestCase):
    """
    Validates Day 17-18 acceptance criteria:
    - Answers cite their sources with SourceReference identifiers.
    - When there is no supporting evidence, the response says so explicitly instead of guessing.
    """

    def setUp(self):
        self.session_id = "test-session-grounding-102"
        self.correlation_id = "corr-grounding-abc-123"
        self.reasoner = MockReasoningEngine(mock_mode=True, simulated_delay_ms=0.0)

        # Setup capture adapter and generate synthetic frame
        self.adapter = ScreenCaptureAdapter(session_id=self.session_id)
        self.adapter.grant_consent_and_enable()
        self.adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)
        self.producer = ObservationProducer(capture_adapter=self.adapter)
        self.observation = self.producer.process_frame()
        self.context_item = self.observation.to_context_item()

    def test_grounded_answer_cites_sources(self):
        """Query with matching context returns answer with explicit SourceReference citations."""
        req = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="What is my CS101 grade?",
            context_items=[self.context_item],
            prompt_version="1.2.0",
        )

        res = self.reasoner.execute_reasoning(req)
        self.assertTrue(res.has_sufficient_evidence)
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)
        self.assertGreater(res.confidence, 0.85)
        self.assertIn("CS101", res.response_text)
        self.assertIn("A", res.response_text)

        # Citations must be present and linked
        self.assertGreater(len(res.sources_used), 0)
        source = res.sources_used[0]
        self.assertEqual(source.source_type, SourceType.SYNTHETIC_SCREEN)
        self.assertIsNotNone(source.source_id)

    def test_no_evidence_response_when_topic_absent(self):
        """When query asks about information not present on screen, returns honest no-evidence response."""
        req = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="How much tuition fee do I owe for next semester?",
            context_items=[self.context_item],  # Only has grades, no tuition
            prompt_version="1.2.0",
        )

        res = self.reasoner.execute_reasoning(req)
        self.assertFalse(res.has_sufficient_evidence)
        self.assertEqual(res.confidence_level, ConfidenceLevel.UNKNOWN)
        self.assertEqual(res.confidence, 0.0)
        self.assertEqual(len(res.sources_used), 0)

        # Must explicitly state insufficient evidence instead of hallucinating a number
        self.assertIn("do not have sufficient evidence", res.response_text.lower())
        self.assertIsNotNone(res.uncertainty_reason)
        self.assertIn("Insufficient evidence", res.uncertainty_reason)

    def test_no_evidence_response_with_empty_context(self):
        """Zero context items immediately produces an honest uncertainty response."""
        req = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="What time is my math class?",
            context_items=[],  # Empty context
            prompt_version="1.2.0",
        )

        res = self.reasoner.execute_reasoning(req)
        self.assertFalse(res.has_sufficient_evidence)
        self.assertEqual(res.confidence_level, ConfidenceLevel.UNKNOWN)
        self.assertTrue(
            "cannot" in res.response_text.lower() or "do not have sufficient" in res.response_text.lower()
        )
        self.assertEqual(len(res.sources_used), 0)


if __name__ == "__main__":
    unittest.main()
