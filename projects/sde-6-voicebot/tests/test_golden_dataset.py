"""
Golden Test Set Suite for Grounding, Source References, No-Evidence and Injection Defenses
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 4 / Days 22-24)
Student: Prathibhashree K

Acceptance Criteria:
- The golden test set checks grounded answers, source references, no-evidence responses
  and prompt-injection resistance, and runs in CI in mock mode.
- Validates against formal expected ground truth in `data/golden_test_set.json`.
"""

import json
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
from contracts.context import (
    ScreenContext,
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
)
from voicebot.context.synthetic_frames import SyntheticFrameGenerator, SyntheticFixture
from voicebot.context.capture_adapter import ScreenCaptureAdapter
from voicebot.context.observation_adapter import ObservationProducer
from voicebot.reasoning.mock_reasoner import MockReasoningEngine


class TestGoldenDataset(unittest.TestCase):
    """
    Executes all golden test cases defined in data/golden_test_set.json.
    """

    @classmethod
    def setUpClass(cls):
        golden_file = project_root / "data" / "golden_test_set.json"
        with open(golden_file, "r", encoding="utf-8") as f:
            cls.cases = json.load(f)
        cls.reasoner = MockReasoningEngine(mock_mode=True, simulated_delay_ms=0.0)

    def _get_context_items(self, fixture_name: str, session_id: str, injected_text: str = None) -> list:
        if not fixture_name:
            return []

        if fixture_name == "injected_screen":
            src = SourceReference(
                source_id="src_inj_frame",
                source_type=SourceType.SYNTHETIC_SCREEN,
                title="Suspicious Window Screen",
                snippet=injected_text,
            )
            return [
                ContextItem(
                    item_id="item-inj-1",
                    item_type=ContextItemType.OCR_TEXT,
                    content=injected_text,
                    source=src,
                )
            ]

        fixture_map = {
            "student_grades": SyntheticFixture.STUDENT_GRADES,
            "course_schedule": SyntheticFixture.COURSE_SCHEDULE,
            "library_loans": SyntheticFixture.LIBRARY_LOANS,
        }

        fixture_enum = fixture_map[fixture_name]
        adapter = ScreenCaptureAdapter(session_id=session_id)
        adapter.grant_consent_and_enable()
        adapter.set_fixture(fixture_enum)
        producer = ObservationProducer(capture_adapter=adapter)
        obs = producer.process_frame()
        return [obs.to_context_item()] if obs else []

    def test_run_all_golden_cases(self):
        """Runs each test in the golden set and asserts strict compliance."""
        for case in self.cases:
            case_id = case["case_id"]
            desc = case["description"]
            fixture = case.get("fixture")
            injected = case.get("injected_text")
            query = case["query"]
            expected = case["expected"]

            with self.subTest(case_id=case_id, description=desc):
                items = self._get_context_items(
                    fixture_name=fixture,
                    session_id=f"session-golden-{case_id}",
                    injected_text=injected,
                )

                req = ReasoningRequest.create(
                    session_id=f"session-golden-{case_id}",
                    correlation_id=f"corr-{case_id}",
                    user_query=query,
                    context_items=items,
                    prompt_version="1.2.0",
                )

                result = self.reasoner.execute_reasoning(req)

                # 1. Evidence sufficiency check
                self.assertEqual(
                    result.has_sufficient_evidence,
                    expected["has_sufficient_evidence"],
                    f"[{case_id}] Mismatch in has_sufficient_evidence",
                )

                # 2. Confidence level check
                self.assertEqual(
                    result.confidence_level.value,
                    expected["confidence_level"],
                    f"[{case_id}] Mismatch in confidence_level",
                )

                # 3. Minimum / maximum confidence thresholds
                if "min_confidence" in expected:
                    self.assertGreaterEqual(
                        result.confidence,
                        expected["min_confidence"],
                        f"[{case_id}] Confidence {result.confidence} below min {expected['min_confidence']}",
                    )
                if "max_confidence" in expected:
                    self.assertLessEqual(
                        result.confidence,
                        expected["max_confidence"],
                        f"[{case_id}] Confidence {result.confidence} exceeds max {expected['max_confidence']}",
                    )

                # 4. Mandatory content substrings
                for term in expected.get("must_contain", []):
                    self.assertIn(
                        term.lower(),
                        result.response_text.lower(),
                        f"[{case_id}] Missing required term '{term}' in response '{result.response_text}'",
                    )

                # 5. Source citations check
                if expected.get("requires_sources"):
                    self.assertGreater(
                        len(result.sources_used),
                        0,
                        f"[{case_id}] Expected cited sources but found none",
                    )
                    expected_source_type = expected.get("source_type")
                    if expected_source_type:
                        self.assertEqual(
                            result.sources_used[0].source_type.value,
                            expected_source_type,
                        )
                else:
                    self.assertEqual(
                        len(result.sources_used),
                        0,
                        f"[{case_id}] Expected zero sources cited for ungrounded/injected query",
                    )

                # 6. Uncertainty reason check
                if "uncertainty_reason_contains" in expected:
                    self.assertIsNotNone(
                        result.uncertainty_reason,
                        f"[{case_id}] Expected uncertainty_reason to be populated",
                    )
                    self.assertIn(
                        expected["uncertainty_reason_contains"].lower(),
                        result.uncertainty_reason.lower(),
                    )


if __name__ == "__main__":
    unittest.main()
