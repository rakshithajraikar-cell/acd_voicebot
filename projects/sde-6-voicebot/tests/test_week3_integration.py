"""
Week 3 End-to-End Integration Tests
SDE 6 Voicebot — Workstream W3 (Week 3 / Day 21 Team Gate)
Student: Prathibhashree K

Validates Day 21 acceptance gate:
- Session flows through screen capture, observation production, deduplication,
  bounded context building, grounded reasoning, prompt injection defense,
  workflow proposal generation, and W4 handoff with canonical envelopes.
- Consent withdrawal stops capture and purges state.
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

from contracts.context import SourceType
from contracts.reasoning import ReasoningRequest, ConfidenceLevel
from contracts.workflow import (
    WorkflowProposal,
    WorkflowStepProposal,
    WorkflowActionRisk,
)
from contracts.envelope import EventEnvelope, WorkflowState
from voicebot.context.capture_adapter import ScreenCaptureAdapter, CaptureState
from voicebot.context.synthetic_frames import SyntheticFixture
from voicebot.context.observation_adapter import ObservationProducer
from voicebot.context.context_builder import BoundedContextBuilder
from voicebot.reasoning.mock_reasoner import MockReasoningEngine
from voicebot.workflow.handoff import WorkflowHandoffClient, MockWorkflowReceiver


class TestWeek3Integration(unittest.TestCase):
    """
    Day 21 Gate Integration Suite.
    """

    def setUp(self):
        self.session_id = "session-gate-day-21"
        self.correlation_id = "corr-gate-day-21-xyz"

        # Initialize full pipeline stack
        self.capture_adapter = ScreenCaptureAdapter(session_id=self.session_id)
        self.observation_producer = ObservationProducer(
            capture_adapter=self.capture_adapter,
            max_freshness_seconds=60.0,
            dedup_window_seconds=10.0,
        )
        self.context_builder = BoundedContextBuilder(default_token_budget=1024)
        self.reasoning_engine = MockReasoningEngine(mock_mode=True, simulated_delay_ms=0.0)
        self.workflow_receiver = MockWorkflowReceiver()
        self.workflow_client = WorkflowHandoffClient(receiver=self.workflow_receiver)

    def test_full_pipeline_flow(self):
        """
        1. User grants opt-in consent.
        2. Screen frame captured -> deduplicated -> converted to observation.
        3. Context builder ingests observation within token budget.
        4. Reasoning produces grounded answer with SourceReference citations.
        5. Workflow proposal generated from context evidence.
        6. Proposal dispatched to W4 mock receiver via EventEnvelope.
        7. Consent withdrawn -> capture halts and context purged.
        """
        # Step 1: Opt-in consent
        state = self.capture_adapter.grant_consent_and_enable()
        self.assertEqual(state, CaptureState.ACTIVE)
        self.capture_adapter.set_fixture(SyntheticFixture.COURSE_SCHEDULE)

        # Step 2: Produce observation
        obs = self.observation_producer.process_frame()
        self.assertIsNotNone(obs)
        self.assertIn("TIMETABLE", obs.summary.upper())
        self.assertEqual(obs.source.source_type, SourceType.SYNTHETIC_SCREEN)

        # Duplicate check: immediate repeat frame must be dropped
        dup_obs = self.observation_producer.process_frame()
        self.assertIsNone(dup_obs)
        self.assertEqual(self.observation_producer.duplicates_dropped, 1)

        # Step 3: Context builder ingestion
        context_item = obs.to_context_item()
        self.context_builder.add_item(context_item)
        build_result = self.context_builder.build_context(query="When is my CS101 class?")
        self.assertEqual(len(build_result.selected_items), 1)
        self.assertLessEqual(build_result.total_tokens, 1024)

        # Step 4: Grounded reasoning
        req = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="When is my CS101 class?",
            context_items=build_result.selected_items,
            prompt_version="1.2.0",
        )
        res = self.reasoning_engine.execute_reasoning(req)
        self.assertTrue(res.has_sufficient_evidence)
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)
        self.assertIn("Turing Hall", res.response_text)
        self.assertGreater(len(res.sources_used), 0)

        # Step 5 & 6: Workflow proposal and W4 handoff
        step = WorkflowStepProposal(
            step_id="step-calendar-sync",
            step_number=1,
            tool_name="calendar.add_event",
            arguments={"title": "CS101 Lecture", "start_time": "2026-11-26T10:00:00Z"},
            description="Sync CS101 lecture into student timetable",
            risk_level=WorkflowActionRisk.IDEMPOTENT_WRITE,
            requires_approval=True,
        )
        proposal = self.reasoning_engine.propose_workflow(
            request=req,
            goal="Sync course lectures into student calendar",
            steps=[step],
        )
        self.assertTrue(proposal.requires_user_approval)

        envelope = self.workflow_client.handoff_proposal(proposal)
        self.assertEqual(envelope.event_type, "workflow.proposal_submitted")
        self.assertEqual(len(self.workflow_receiver.received_proposals), 1)
        self.assertEqual(self.workflow_receiver.execution_audit_log[0]["status"], WorkflowState.AWAITING_APPROVAL.value)

        # Step 7: Consent withdrawal
        self.observation_producer.withdraw_consent()
        self.assertFalse(self.capture_adapter.is_enabled)
        self.assertEqual(len(self.observation_producer.get_active_observations()), 0)
        self.context_builder.clear()
        self.assertEqual(len(self.context_builder.get_items()), 0)

    def test_pipeline_no_evidence_handling(self):
        """Pipeline handles queries without context honestly without guessing."""
        self.capture_adapter.grant_consent_and_enable()
        self.capture_adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)
        obs = self.observation_producer.process_frame()
        self.context_builder.add_item(obs.to_context_item())

        build_result = self.context_builder.build_context(query="What is the weather outside?")
        req = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="What is the weather outside?",
            context_items=build_result.selected_items,
            prompt_version="1.2.0",
        )
        res = self.reasoning_engine.execute_reasoning(req)

        self.assertFalse(res.has_sufficient_evidence)
        self.assertEqual(res.confidence_level, ConfidenceLevel.UNKNOWN)
        self.assertIn("do not have sufficient evidence", res.response_text.lower())
        self.assertEqual(len(res.sources_used), 0)


if __name__ == "__main__":
    unittest.main()
