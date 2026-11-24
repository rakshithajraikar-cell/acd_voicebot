"""
Tests for Screen Context Consent Revocation and Memory Clearance
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 4 / Days 25-27)
Student: Prathibhashree K

Acceptance Criteria:
- A test proves that withdrawing consent stops new capture and clears stored context.
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

from voicebot.context.capture_adapter import ScreenCaptureAdapter, CaptureState
from voicebot.context.synthetic_frames import SyntheticFixture
from voicebot.context.observation_adapter import ObservationProducer
from voicebot.context.context_builder import BoundedContextBuilder


class TestConsentRevocation(unittest.TestCase):
    """
    Validates complete lifecycle and memory purging on user consent revocation.
    """

    def setUp(self):
        self.session_id = "session-consent-test-99"
        self.adapter = ScreenCaptureAdapter(session_id=self.session_id)
        self.producer = ObservationProducer(capture_adapter=self.adapter)
        self.builder = BoundedContextBuilder()

    def test_withdrawing_consent_stops_capture_and_clears_stored_context(self):
        """Proves that withdrawing consent stops new capture and clears stored context."""
        # 1. Initially disabled
        self.assertFalse(self.adapter.is_enabled)
        self.assertFalse(self.adapter.has_consent)

        # 2. Grant consent and capture active frames
        self.adapter.grant_consent_and_enable()
        self.adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)
        self.assertTrue(self.adapter.is_enabled)
        self.assertTrue(self.adapter.has_consent)

        obs = self.producer.process_frame()
        self.assertIsNotNone(obs)
        self.assertEqual(len(self.producer.get_active_observations()), 1)

        # Ingest observation into context builder
        self.builder.add_item(obs.to_context_item())
        self.assertEqual(len(self.builder.get_items()), 1)

        # 3. WITHDRAW CONSENT
        revoked_state = self.producer.withdraw_consent()
        self.builder.clear()

        # A. State transition
        self.assertEqual(revoked_state, CaptureState.CONSENT_REVOKED)
        self.assertFalse(self.adapter.is_enabled)
        self.assertFalse(self.adapter.has_consent)

        # B. Memory purging: all stored observations and context items are completely cleared
        self.assertEqual(len(self.producer.get_active_observations()), 0)
        self.assertEqual(len(self.builder.get_items()), 0)

        # C. Subsequent captures fail / return None
        obs_blocked = self.producer.process_frame()
        self.assertIsNone(obs_blocked)

        frame_blocked = self.adapter.capture_frame()
        self.assertFalse(frame_blocked.capture_enabled)
        self.assertFalse(frame_blocked.capture_allowed_by_user)
        self.assertIsNone(frame_blocked.ocr_text)


if __name__ == "__main__":
    unittest.main()
