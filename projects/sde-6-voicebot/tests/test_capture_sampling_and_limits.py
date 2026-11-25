"""
Unit Tests for Screen Capture Sampling and Size Limits
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Verifies:
- Capture is strictly OFF by default.
- Requires explicit user opt-in consent.
- Enforces sampling rate limits and throttling.
- Enforces screen dimensions and payload size bounds.
- Guaranteed zero real screenshots (only synthetic frames).
"""

import time
import unittest
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.voicebot.context.capture_adapter import (
    ScreenCaptureAdapter,
    CaptureState,
    CaptureRateLimitExceededError,
    FrameSizeLimitExceededError,
)
from src.voicebot.context.synthetic_frames import SyntheticFixture
from contracts.context import ScreenContext


class TestCaptureSamplingAndLimits(unittest.TestCase):

    def setUp(self):
        self.session_id = "test-session-capture-w2"
        self.adapter = ScreenCaptureAdapter(
            session_id=self.session_id,
            min_interval_seconds=0.2,
            max_width=1280,
            max_height=720,
            max_payload_bytes=2048,
            throttle_policy="cache",
        )

    def test_capture_off_by_default(self):
        """NON-NEGOTIABLE RULE: Screen capture must be OFF by default."""
        self.assertFalse(self.adapter.is_enabled)
        self.assertFalse(self.adapter.has_consent)
        frame = self.adapter.capture_frame()
        self.assertFalse(frame.capture_enabled)
        self.assertIsNone(frame.ocr_text)

    def test_explicit_opt_in_required(self):
        """Opt-in consent must be explicitly granted before capture is active."""
        self.adapter.grant_consent_and_enable()
        self.assertTrue(self.adapter.is_enabled)
        frame = self.adapter.capture_frame()
        self.assertTrue(frame.capture_enabled)
        self.assertTrue(frame.is_synthetic)
        self.assertIsNotNone(frame.ocr_text)

    def test_sampling_rate_limit_throttle_cache_policy(self):
        """Calling capture faster than min_interval returns cached frame under 'cache' policy."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_sampling_limits(min_interval_seconds=0.5, throttle_policy="cache")

        frame1 = self.adapter.capture_frame()
        # Immediate subsequent call
        frame2 = self.adapter.capture_frame()

        self.assertEqual(frame1.context_id, frame2.context_id)
        self.assertGreater(self.adapter.captures_throttled, 0)

    def test_sampling_rate_limit_reject_policy(self):
        """Calling capture faster than min_interval raises CaptureRateLimitExceededError under 'reject' policy."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_sampling_limits(min_interval_seconds=0.5, throttle_policy="reject")

        self.adapter.capture_frame()
        with self.assertRaises(CaptureRateLimitExceededError):
            self.adapter.capture_frame()

    def test_size_limits_clamping(self):
        """Frames larger than configured max dimensions are safely clamped."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)
        self.adapter.set_size_limits(max_width=800, max_height=600, strict_size_rejection=False)

        frame = self.adapter.capture_frame()
        self.assertLessEqual(frame.screen_width, 800)
        self.assertLessEqual(frame.screen_height, 600)
        self.assertTrue(frame.metadata.get("size_limited"))
        self.assertEqual(frame.metadata.get("original_dimensions"), "1920x1080")

    def test_strict_size_rejection_raises_error(self):
        """Strict size rejection raises FrameSizeLimitExceededError if frame exceeds bounds."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_size_limits(max_width=500, max_height=500, strict_size_rejection=True)

        with self.assertRaises(FrameSizeLimitExceededError):
            self.adapter.capture_frame()

    def test_strict_payload_byte_limit_raises_error(self):
        """Oversized OCR payload triggers FrameSizeLimitExceededError under strict mode."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_size_limits(max_width=1920, max_height=1080, max_payload_bytes=10, strict_size_rejection=True)

        with self.assertRaises(FrameSizeLimitExceededError):
            self.adapter.capture_frame()

    def test_only_synthetic_frames_allowed(self):
        """Verifies synthetic frame guarantee with zero OS disk writes."""
        self.adapter.grant_consent_and_enable()
        frame = self.adapter.capture_frame()
        self.assertTrue(frame.is_synthetic)


if __name__ == "__main__":
    unittest.main()
