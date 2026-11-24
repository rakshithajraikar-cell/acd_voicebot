"""
Tests for Timestamped, Source-Linked Observations, Deduplication, Staleness, and Consent Withdrawal
SDE 6 Voicebot — Workstream W3 (Week 3 / Days 15-16)
Student: Prathibhashree K
"""

import datetime
import unittest

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_root = project_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from contracts.context import ScreenContext, SourceType, BoundingBox
from voicebot.context.capture_adapter import ScreenCaptureAdapter, CaptureState
from voicebot.context.synthetic_frames import SyntheticFixture, SyntheticFrameGenerator
from voicebot.context.observation_adapter import Observation, ObservationProducer


class TestObservationsDedupAndConsent(unittest.TestCase):
    """
    Validates Day 15-16 acceptance criteria:
    - Every observation has a timestamp and source reference.
    - Stale frames are dropped.
    - Duplicate frames are dropped.
    - Withdrawing consent stops capture and clears pending context.
    """

    def setUp(self):
        self.session_id = "test-session-obs-101"
        self.adapter = ScreenCaptureAdapter(session_id=self.session_id)
        self.producer = ObservationProducer(
            capture_adapter=self.adapter,
            max_freshness_seconds=30.0,
            dedup_window_seconds=5.0,
        )

    def test_observation_creation_and_fields(self):
        """Every observation must have a timestamp and source reference."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)

        obs = self.producer.process_frame()
        self.assertIsNotNone(obs)
        self.assertIsInstance(obs, Observation)
        self.assertIsNotNone(obs.observation_id)
        self.assertIsNotNone(obs.timestamp)
        self.assertIsNotNone(obs.source)
        self.assertIsNotNone(obs.source.source_id)
        self.assertEqual(obs.source.source_type, SourceType.SYNTHETIC_SCREEN)
        self.assertTrue(obs.is_synthetic)
        self.assertIn("STUDENT ACADEMIC PORTAL", obs.summary.upper())

        # Test serialization
        d = obs.to_dict()
        restored = Observation.from_dict(d)
        self.assertEqual(restored.observation_id, obs.observation_id)
        self.assertEqual(restored.source.source_id, obs.source.source_id)

    def test_observation_to_context_item_bridge(self):
        """Observations convert smoothly to ContextItems preserving SourceReference."""
        self.adapter.grant_consent_and_enable()
        obs = self.producer.process_frame()
        self.assertIsNotNone(obs)

        item = obs.to_context_item(ttl_seconds=120)
        self.assertEqual(item.source.source_id, obs.source.source_id)
        self.assertEqual(item.ttl_seconds, 120)
        self.assertTrue(item.is_synthetic)
        self.assertIn("Observation:", item.content)

    def test_duplicate_frame_detection_and_dropping(self):
        """Duplicate frames within dedup window are detected and dropped."""
        self.adapter.grant_consent_and_enable()
        self.adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)

        # First frame should produce observation
        obs1 = self.producer.process_frame()
        self.assertIsNotNone(obs1)
        self.assertEqual(self.producer.observations_produced, 1)
        self.assertEqual(self.producer.duplicates_dropped, 0)

        # Processing identical frame within dedup window must be dropped
        obs2 = self.producer.process_frame()
        self.assertIsNone(obs2)
        self.assertEqual(self.producer.duplicates_dropped, 1)

        # Changing fixture yields new content hash and produces a new observation
        self.adapter.set_fixture(SyntheticFixture.COURSE_SCHEDULE)
        obs3 = self.producer.process_frame()
        self.assertIsNotNone(obs3)
        self.assertEqual(self.producer.observations_produced, 2)
        self.assertIn("Timetable", obs3.summary)

    def test_stale_frame_detection_and_dropping(self):
        """Frames older than max_freshness_seconds are dropped as stale."""
        self.adapter.grant_consent_and_enable()

        now = datetime.datetime.now(datetime.timezone.utc)
        # Create a synthetic frame that is 120 seconds old
        old_time = (now - datetime.timedelta(seconds=120)).isoformat()
        stale_frame = ScreenContext.create_synthetic(
            session_id=self.session_id,
            window_title="Old Stale Window",
            application_name="OldApp",
            ocr_text="Some old data from minutes ago",
            capture_allowed_by_user=True,
            capture_enabled=True,
        )
        # Force stale timestamp
        stale_frame = ScreenContext(
            context_id=stale_frame.context_id,
            session_id=stale_frame.session_id,
            timestamp=old_time,
            capture_enabled=True,
            capture_allowed_by_user=True,
            window_title=stale_frame.window_title,
            application_name=stale_frame.application_name,
            screen_width=stale_frame.screen_width,
            screen_height=stale_frame.screen_height,
            ocr_text=stale_frame.ocr_text,
            is_synthetic=True,
        )

        obs = self.producer.process_frame(frame=stale_frame, now=now)
        self.assertIsNone(obs)
        self.assertEqual(self.producer.stale_dropped, 1)

    def test_consent_withdrawal_stops_capture_and_clears_context(self):
        """Withdrawing consent stops capture and immediately clears pending context."""
        self.adapter.grant_consent_and_enable()
        obs = self.producer.process_frame()
        self.assertIsNotNone(obs)
        self.assertEqual(len(self.producer.get_active_observations()), 1)

        # Withdraw consent
        state = self.producer.withdraw_consent()
        self.assertEqual(state, CaptureState.CONSENT_REVOKED)
        self.assertFalse(self.adapter.is_enabled)
        self.assertFalse(self.adapter.has_consent)

        # Retained observations must be completely purged
        self.assertEqual(len(self.producer.get_active_observations()), 0)

        # Subsequent capture without consent must return None
        obs_after = self.producer.process_frame()
        self.assertIsNone(obs_after)


if __name__ == "__main__":
    unittest.main()
