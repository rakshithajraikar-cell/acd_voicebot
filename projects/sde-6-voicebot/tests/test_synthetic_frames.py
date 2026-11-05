"""
Unit Tests for Synthetic Frames & Capture Adapter
Workstream W3 — Student: Prathibhashree K
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.voicebot.context.capture_adapter import ScreenCaptureAdapter, CaptureState
from src.voicebot.context.synthetic_frames import SyntheticFrameGenerator, SyntheticFixture
from contracts.context import SourceType


class TestSyntheticFrames(unittest.TestCase):
    """
    Verifies that screen capture is disabled by default,
    requires opt-in consent, and strictly uses synthetic fixtures without personal data.
    """

    def setUp(self):
        self.session_id = "test-session-001"
        self.adapter = ScreenCaptureAdapter(self.session_id)

    def test_screen_capture_off_by_default(self):
        """NON-NEGOTIABLE RULE: Screen capture must be OFF by default."""
        self.assertFalse(self.adapter.is_enabled)
        self.assertFalse(self.adapter.has_consent)

        frame = self.adapter.capture_frame()
        self.assertFalse(frame.capture_enabled)
        self.assertFalse(frame.capture_allowed_by_user)
        self.assertIsNone(frame.ocr_text, "OCR text must not be exposed when capture is disabled")
        self.assertEqual(len(frame.bounding_boxes), 0)

        status = self.adapter.get_indicator_state()
        self.assertEqual(status["state"], CaptureState.OFF.value)
        self.assertEqual(status["indicator_color"], "gray")

    def test_explicit_consent_opt_in(self):
        """Scenario 3: Requires user action to enable."""
        # User grants consent
        state = self.adapter.grant_consent_and_enable()
        self.assertEqual(state, CaptureState.ACTIVE)
        self.assertTrue(self.adapter.is_enabled)
        self.assertTrue(self.adapter.has_consent)

        frame = self.adapter.capture_frame()
        self.assertTrue(frame.capture_enabled)
        self.assertTrue(frame.capture_allowed_by_user)
        self.assertTrue(frame.is_synthetic)
        self.assertIsNotNone(frame.ocr_text)
        self.assertIn("CS101", frame.ocr_text)

        status = self.adapter.get_indicator_state()
        self.assertEqual(status["state"], CaptureState.ACTIVE.value)
        self.assertEqual(status["indicator_color"], "green")

    def test_consent_withdrawal_stops_capture(self):
        """Scenario 3: Withdrawing consent immediately stops new capture."""
        self.adapter.grant_consent_and_enable()
        self.assertTrue(self.adapter.is_enabled)

        # User withdraws consent
        state = self.adapter.withdraw_consent()
        self.assertEqual(state, CaptureState.CONSENT_REVOKED)
        self.assertFalse(self.adapter.is_enabled)
        self.assertFalse(self.adapter.has_consent)

        # Subsequent capture call yields blank/disabled frame
        frame = self.adapter.capture_frame()
        self.assertFalse(frame.capture_enabled)
        self.assertIsNone(frame.ocr_text)

    def test_fixtures_generation_and_grounding_references(self):
        """Verifies synthetic frame fixtures produce valid mock data."""
        for fixture in SyntheticFixture:
            ctx = SyntheticFrameGenerator.generate_screen_context(
                session_id=self.session_id,
                fixture=fixture,
                capture_allowed_by_user=True,
                capture_enabled=True,
            )
            self.assertTrue(ctx.is_synthetic)
            self.assertGreater(ctx.screen_width, 0)
            self.assertGreater(ctx.screen_height, 0)

            items = SyntheticFrameGenerator.generate_context_items(self.session_id, fixture)
            if fixture != SyntheticFixture.BLANK_DESKTOP:
                self.assertGreater(len(items), 0)
                item = items[0]
                self.assertTrue(item.is_synthetic)
                self.assertEqual(item.source.source_type, SourceType.SYNTHETIC_SCREEN)
                self.assertTrue(item.source.uri.startswith("synthetic://"))


if __name__ == "__main__":
    unittest.main()
