"""
Tests for WorkflowProposal Schema Validation and Handoff to Workflow Module (W4)
SDE 6 Voicebot — Workstream W3 to W4 Integration (Week 3 / Days 19-20)
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

from contracts.workflow import (
    WorkflowProposal,
    WorkflowStepProposal,
    WorkflowActionRisk,
)
from contracts.context import SourceReference, SourceType
from contracts.reasoning import ReasoningRequest
from contracts.envelope import EventEnvelope, WorkflowState
from voicebot.reasoning.mock_reasoner import MockReasoningEngine
from voicebot.workflow.handoff import (
    WorkflowHandoffClient,
    MockWorkflowReceiver,
    WorkflowHandoffError,
    validate_workflow_proposal,
)


class TestWorkflowProposalHandoff(unittest.TestCase):
    """
    Validates Day 19-20 acceptance criteria:
    - A schema-validated WorkflowProposal is handed to the workflow module end to end in mock mode.
    - Consequential actions require explicit user approval.
    - Only allow-listed tools may be proposed.
    - Wrapped in canonical EventEnvelope.
    """

    def setUp(self):
        self.session_id = "test-session-wf-handoff"
        self.correlation_id = "corr-wf-789"
        self.reasoner = MockReasoningEngine(mock_mode=True, simulated_delay_ms=0.0)

        self.receiver = MockWorkflowReceiver()
        self.client = WorkflowHandoffClient(receiver=self.receiver)

        self.source = SourceReference(
            source_id="src_grades_ref",
            source_type=SourceType.SYNTHETIC_SCREEN,
            title="Student Academic Portal",
            snippet="Course: CS101 Grade: A",
        )

    def test_workflow_proposal_creation_and_fields(self):
        """WorkflowProposal creates immutable valid payload with sources and steps."""
        step = WorkflowStepProposal(
            step_id="step-1",
            step_number=1,
            tool_name="calendar.add_event",
            arguments={"title": "CS101 Office Hours", "start_time": "2026-11-25T10:00:00Z"},
            description="Add office hours to student calendar",
            risk_level=WorkflowActionRisk.IDEMPOTENT_WRITE,
            requires_approval=True,
        )

        proposal = WorkflowProposal.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            goal="Schedule study session for CS101",
            suggested_action="PROPOSE_SCHEDULE_STUDY_SESSION",
            steps=[step],
            sources_used=[self.source],
            confidence=0.95,
        )

        self.assertEqual(proposal.goal, "Schedule study session for CS101")
        self.assertEqual(len(proposal.steps), 1)
        self.assertTrue(proposal.requires_user_approval)
        self.assertTrue(proposal.is_mock)

        # Test dictionary roundtrip
        d = proposal.to_dict()
        restored = WorkflowProposal.from_dict(d)
        self.assertEqual(restored.proposal_id, proposal.proposal_id)
        self.assertEqual(restored.steps[0].tool_name, "calendar.add_event")

    def test_reasoning_engine_proposes_workflow(self):
        """MockReasoningEngine.propose_workflow generates grounded proposal."""
        req = ReasoningRequest.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            user_query="Can you help me renew my overdue library book?",
            prompt_version="1.2.0",
        )

        step = WorkflowStepProposal(
            step_id="step-renew-1",
            step_number=1,
            tool_name="library.renew_book",
            arguments={"book_title": "Introduction to Algorithms", "renewal_days": 14},
            description="Renew library book for 14 additional days",
            risk_level=WorkflowActionRisk.IDEMPOTENT_WRITE,
            requires_approval=True,
        )

        proposal = self.reasoner.propose_workflow(
            request=req,
            goal="Renew borrowed library textbook",
            steps=[step],
        )

        self.assertEqual(proposal.session_id, self.session_id)
        self.assertEqual(proposal.goal, "Renew borrowed library textbook")
        self.assertEqual(len(proposal.steps), 1)

    def test_allow_listed_tool_validation(self):
        """Only allow-listed tools may run; unlisted tools are rejected with error."""
        unauthorized_step = WorkflowStepProposal(
            step_id="step-bad",
            step_number=1,
            tool_name="unauthorized_system_shell",
            arguments={"cmd": "rm -rf /"},
            description="Execute shell command",
            requires_approval=False,
        )

        bad_proposal = WorkflowProposal.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            goal="Run unapproved script",
            suggested_action="PROPOSE_RUN_SCRIPT",
            steps=[unauthorized_step],
            sources_used=[self.source],
        )

        with self.assertRaises(WorkflowHandoffError) as ctx:
            validate_workflow_proposal(bad_proposal)
        self.assertIn("not in the allow-list", str(ctx.exception))

    def test_consequential_action_approval_gate_enforced(self):
        """Non-negotiable rule: consequential actions cannot bypass user approval."""
        email_step = WorkflowStepProposal(
            step_id="step-email",
            step_number=1,
            tool_name="email.draft",
            arguments={"to": "prof@university.edu", "subject": "Exam query", "body": "Hello professor"},
            description="Send an email to advisor",
            risk_level=WorkflowActionRisk.CONSEQUENTIAL,
            requires_approval=False,  # Attempting to bypass approval gate!
        )

        proposal = WorkflowProposal.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            goal="Email course instructor",
            suggested_action="PROPOSE_SEND_EMAIL",
            steps=[email_step],
            sources_used=[self.source],
        )

        with self.assertRaises(WorkflowHandoffError) as ctx:
            validate_workflow_proposal(proposal)
        self.assertIn("must require user approval", str(ctx.exception))

    def test_end_to_end_handoff_to_mock_receiver(self):
        """Valid proposal is handed off via EventEnvelope and recorded in receiver audit log."""
        step = WorkflowStepProposal(
            step_id="step-ok",
            step_number=1,
            tool_name="academic.export_grades",
            arguments={"semester": "Fall 2026", "format": "pdf"},
            description="Generate official PDF report of grades",
            risk_level=WorkflowActionRisk.READ_ONLY,
            requires_approval=False,
        )

        proposal = WorkflowProposal.create(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            goal="Export semester grades transcript",
            suggested_action="PROPOSE_EXPORT_TRANSCRIPT",
            steps=[step],
            sources_used=[self.source],
        )

        envelope = self.client.handoff_proposal(proposal)

        # Check returned EventEnvelope
        self.assertIsInstance(envelope, EventEnvelope)
        self.assertEqual(envelope.event_type, "workflow.proposal_submitted")
        self.assertEqual(envelope.producer, "w3.context_reasoning")
        self.assertEqual(envelope.session_id, self.session_id)

        # Verify receiver recorded proposal
        self.assertEqual(len(self.receiver.received_proposals), 1)
        self.assertEqual(len(self.receiver.execution_audit_log), 1)
        audit = self.receiver.execution_audit_log[0]
        self.assertEqual(audit["proposal_id"], proposal.proposal_id)
        self.assertEqual(audit["goal"], "Export semester grades transcript")


if __name__ == "__main__":
    unittest.main()
