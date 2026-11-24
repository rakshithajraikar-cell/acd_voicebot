"""
Unit Tests for Vision / OCR Adapter Interface and Mock
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Verifies:
- VisionAdapterInterface contracts and abstract methods.
- MockVisionOCRAdapter deterministic extraction without external libraries.
- Respects privacy boundaries (empty result when capture disabled).
- Extraction of text and UI bounding boxes from synthetic frames.
- Provider health check and failure injection.
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from contracts.context import ScreenContext, BoundingBox
from src.voicebot.context.vision_adapter import (
    VisionAdapterInterface,
    MockVisionOCRAdapter,
    VisionOCRResult,
)
from src.voicebot.context.synthetic_frames import SyntheticFrameGenerator, SyntheticFixture


class TestVisionAdapter(unittest.TestCase):

    def setUp(self):
        self.session_id = "test-session-vision"
        self.adapter = MockVisionOCRAdapter(mock_mode=True, simulated_latency_ms=0.0)

    def test_implements_interface(self):
        """Verifies MockVisionOCRAdapter adheres to VisionAdapterInterface."""
        self.assertIsInstance(self.adapter, VisionAdapterInterface)

    def test_respects_disabled_capture_privacy(self):
        """When screen capture is disabled, vision adapter returns empty extraction."""
        disabled_frame = SyntheticFrameGenerator.generate_screen_context(
            session_id=self.session_id,
            fixture=SyntheticFixture.STUDENT_GRADES,
            capture_allowed_by_user=False,
            capture_enabled=False,
        )
        result = self.adapter.process_frame(disabled_frame)
        self.assertEqual(result.text, "")
        self.assertEqual(len(result.bounding_boxes), 0)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.metadata.get("reason"), "capture_disabled")

    def test_successful_ocr_extraction_on_synthetic_frame(self):
        """Extracts structured text and bounding boxes from enabled synthetic frame."""
        frame = SyntheticFrameGenerator.generate_screen_context(
            session_id=self.session_id,
            fixture=SyntheticFixture.STUDENT_GRADES,
            capture_allowed_by_user=True,
            capture_enabled=True,
        )
        result = self.adapter.process_frame(frame)
        self.assertTrue(result.is_mock)
        self.assertIn("CS101", result.text)
        self.assertIn("STUDENT ACADEMIC PORTAL", result.text)
        self.assertGreater(len(result.bounding_boxes), 0)
        self.assertGreaterEqual(result.confidence, 0.90)

    def test_extract_text_and_detect_elements_convenience_methods(self):
        """Verifies convenience extraction helpers."""
        frame = SyntheticFrameGenerator.generate_screen_context(
            session_id=self.session_id,
            fixture=SyntheticFixture.COURSE_SCHEDULE,
            capture_allowed_by_user=True,
            capture_enabled=True,
        )
        text = self.adapter.extract_text(frame)
        elements = self.adapter.detect_elements(frame)
        self.assertIn("WEEKLY SCHEDULE", text)
        self.assertGreater(len(elements), 0)
        self.assertIsInstance(elements[0], BoundingBox)

    def test_non_synthetic_frame_rejected(self):
        """Privacy guarantee: Rejects non-synthetic frames."""
        unsafe_frame = ScreenContext(
            context_id="unsafe-id",
            session_id=self.session_id,
            timestamp="2026-11-05T00:00:00Z",
            capture_enabled=True,
            capture_allowed_by_user=True,
            is_synthetic=False,  # Unsafe / real frame
        )
        with self.assertRaises(ValueError):
            self.adapter.process_frame(unsafe_frame)

    def test_health_check_and_simulated_failure(self):
        """Verifies health reporting and error simulation."""
        health = self.adapter.check_health()
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["mock_mode"])

        self.adapter.set_failure_mode(True)
        self.assertEqual(self.adapter.check_health()["status"], "degraded")

        frame = SyntheticFrameGenerator.generate_screen_context(
            session_id=self.session_id,
            fixture=SyntheticFixture.STUDENT_GRADES,
            capture_allowed_by_user=True,
            capture_enabled=True,
        )
        with self.assertRaises(RuntimeError):
            self.adapter.process_frame(frame)


if __name__ == "__main__":
    unittest.main()
