"""
Tests for Granular Per-Stage Latency Instrumentation
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 4 / Days 25-27)
Student: Prathibhashree K

Acceptance Criteria:
- Reasoning latency is instrumented per stage, and the numbers are reported.
"""

import time
import unittest

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_root = project_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from voicebot.reasoning.latency import LatencyTracker, LatencyReport


class TestLatencyInstrumentation(unittest.TestCase):
    """
    Validates granular latency measurement across pipeline stages.
    """

    def test_latency_tracker_records_stages(self):
        """Measures each stage and produces a consolidated report."""
        tracker = LatencyTracker()

        # Simulate capture stage
        with tracker.measure("capture"):
            time.sleep(0.005)

        # Simulate OCR stage
        with tracker.measure("ocr"):
            time.sleep(0.003)

        # Simulate context building stage
        with tracker.measure("context_build"):
            time.sleep(0.002)

        # Simulate prompt rendering stage
        with tracker.measure("prompt_render"):
            time.sleep(0.002)

        # Simulate inference stage
        with tracker.measure("inference"):
            time.sleep(0.010)

        # Simulate output validation stage
        with tracker.measure("validation"):
            time.sleep(0.001)

        report = tracker.build_report()
        self.assertIsInstance(report, LatencyReport)

        d = report.to_dict()

        # Validate that all expected stage keys exist
        expected_stages = [
            "capture_ms",
            "ocr_ms",
            "context_build_ms",
            "prompt_render_ms",
            "inference_ms",
            "validation_ms",
            "total_latency_ms",
        ]
        for stage in expected_stages:
            self.assertIn(stage, d)
            self.assertIsInstance(d[stage], float)
            self.assertGreater(d[stage], 0.0, f"Stage {stage} should be > 0.0ms")

        # Total latency must be greater than or equal to the longest single stage
        self.assertGreaterEqual(report.total_latency_ms, report.inference_ms)

    def test_manual_stage_recording(self):
        """Directly recorded durations are reflected in final latency report."""
        tracker = LatencyTracker()
        tracker.record_stage("capture", 12.5)
        tracker.record_stage("ocr", 8.2)
        tracker.record_stage("inference", 45.0)

        report = tracker.build_report()
        self.assertEqual(report.capture_ms, 12.5)
        self.assertEqual(report.ocr_ms, 8.2)
        self.assertEqual(report.inference_ms, 45.0)


if __name__ == "__main__":
    unittest.main()
