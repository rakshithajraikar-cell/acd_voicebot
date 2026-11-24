"""Week 3 Integration Test Suite for Workstream W4 (Agentic Workflow).

Covers Deliverables & Acceptance Criteria for Days 15–21:
- D15–16: Checkpoint & resume, failed-step recovery, idempotency keys
- D17–18: Step-level audit trail and real-time progress events
- D19–20: Reasoning proposals (W3), backend approval state (W5), and UI (W6) integration
- Duplicate and expired approval security guarantees
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest

from sde6_voicebot.contracts.common import WorkflowState, EventEnvelope
from sde6_voicebot.contracts.workflow import (
    ApprovalRequest,
    ApprovalStatus,
    StepStatus,
    WorkflowCheckpoint,
    WorkflowPlan,
    WorkflowProposal,
    WorkflowResult,
    WorkflowStep,
)
from sde6_voicebot.workflow.exceptions import (
    ApprovalExpiredError,
    DuplicateApprovalError,
    WorkflowCancelledError,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import ToolRegistry
from sde6_voicebot.integrations.reasoning_adapter import ReasoningProposalAdapter
from sde6_voicebot.integrations.backend_bridge import BackendApprovalBridge
from sde6_voicebot.integrations.ui_controller import UIWorkflowController


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def harmless_registry() -> ToolRegistry:
    return ToolRegistry(granted_scopes={"safe.memory.read_write", "user.notification.schedule"})


def make_two_step_plan(plan_id: str = "plan-w3-001") -> WorkflowPlan:
    """Create a 2-step plan: Step 1 harmless (format_notes), Step 2 consequential (schedule_reminder)."""
    step1 = WorkflowStep(
        step_id="step-1",
        name="Format Summary Notes",
        tool_name="format_notes",
        arguments={"text": "Meeting discussion notes on AI Voicebot architecture"},
        is_consequential=False,
        is_idempotent=True,
        idempotency_key="format-meeting-001",
    )
    step2 = WorkflowStep(
        step_id="step-2",
        name="Schedule Review Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "Team SDE 6 Sync", "delay_minutes": 30, "priority": "high"},
        depends_on=["step-1"],
        is_consequential=True,
        is_idempotent=False,
        idempotency_key="reminder-meeting-001",
    )
    return WorkflowPlan(
        plan_id=plan_id,
        session_id="session-w3-test",
        correlation_id="corr-w3-test",
        title="Week 3 Test Workflow Plan",
        steps=[step1, step2],
    )


# ---------------------------------------------------------------------------
# 1. Checkpoint & Resume with Failed-Step Recovery (D15–16)
# ---------------------------------------------------------------------------

class TestCheckpointAndResume:
    def test_checkpoint_saves_snapshot_of_execution_state(self, harmless_registry):
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        plan = make_two_step_plan()
        
        # Start workflow - step 1 runs and step 2 awaits approval
        res = executor.start_workflow(plan)
        assert res["status"] == "awaiting_approval"
        
        # Checkpoint should have been created
        assert len(executor.checkpoints) >= 1
        latest_cp = list(executor.checkpoints.values())[-1]
        assert latest_cp.plan_id == plan.plan_id
        assert "step-1" in latest_cp.completed_steps
        assert latest_cp.step_states["step-1"] == StepStatus.SUCCEEDED
        assert latest_cp.step_results["step-1"] is not None

    def test_failed_step_recovery_does_not_rerun_completed_steps(self, harmless_registry):
        """Verify that after a step failure, recovery resumes without re-executing completed steps."""
        execution_counts = {"step-1": 0, "step-2": 0}

        def mock_format(args: Dict[str, Any]) -> Dict[str, Any]:
            execution_counts["step-1"] += 1
            text = args.get("text", "")
            return {"formatted_text": text.upper(), "word_count": len(text.split())}

        fail_step2 = True

        def mock_reminder(args: Dict[str, Any]) -> Dict[str, Any]:
            execution_counts["step-2"] += 1
            if fail_step2:
                raise RuntimeError("Simulated transient connection failure")
            return {"reminder_id": "rem-123", "status": "scheduled", "title": args.get("title", "")}

        # Override handlers
        registry = ToolRegistry(granted_scopes={"safe.memory.read_write", "user.notification.schedule"})
        registry._executors["format_notes"] = mock_format
        registry._executors["schedule_reminder"] = mock_reminder

        executor = WorkflowExecutor(tool_registry=registry)
        plan = make_two_step_plan()

        # Step 1 succeeds; Step 2 pauses at approval
        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # Approve step 2 -> it runs and triggers simulated failure
        res2 = executor.approve_step(req_id)
        assert res2["status"] == "failed"
        assert execution_counts["step-1"] == 1
        assert execution_counts["step-2"] == 1

        # Save checkpoint of failed state
        checkpoint = executor.save_checkpoint(metadata={"reason": "pre-recovery"})
        assert "step-1" in checkpoint.completed_steps
        assert "step-2" in checkpoint.failed_steps

        # Now fix the issue and resume from checkpoint
        fail_step2 = False
        resume_res = executor.resume_workflow(checkpoint=checkpoint, recover_failed=True)

        assert resume_res["status"] == "completed"
        # CRUCIAL ACCEPTANCE CRITERIA: Completed step-1 was NEVER re-run!
        assert execution_counts["step-1"] == 1
        # Step-2 was retried and succeeded
        assert execution_counts["step-2"] == 2
        assert plan.steps[0].status == StepStatus.SUCCEEDED
        assert plan.steps[1].status == StepStatus.SUCCEEDED


# ---------------------------------------------------------------------------
# 2. Idempotency Keys (D15–16)
# ---------------------------------------------------------------------------

class TestIdempotencyKeys:
    def test_idempotency_keys_prevent_duplicate_execution(self, harmless_registry):
        """Verify that identical tool call with same idempotency_key returns cached result without invoking tool."""
        call_count = 0

        def counting_format(args: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            text = args.get("text", "")
            return {"formatted_text": f"Formatted: {text}", "word_count": len(text.split())}

        registry = ToolRegistry(granted_scopes={"safe.memory.read_write"})
        registry._executors["format_notes"] = counting_format

        executor = WorkflowExecutor(tool_registry=registry)

        step1 = WorkflowStep(
            step_id="step-1",
            name="Format Notes First Call",
            tool_name="format_notes",
            arguments={"text": "Quarterly voicebot review"},
            is_consequential=False,
            is_idempotent=True,
            idempotency_key="idem-key-notes-001",
        )
        plan1 = WorkflowPlan(
            plan_id="plan-idem-1",
            session_id="session-idem",
            correlation_id="corr-idem",
            title="First Call Plan",
            steps=[step1],
        )

        # Run first time -> tool executes
        executor.start_workflow(plan1)
        assert call_count == 1
        first_result = step1.result

        # Run second time with identical idempotency_key
        step2 = WorkflowStep(
            step_id="step-2",
            name="Format Notes Duplicate Call",
            tool_name="format_notes",
            arguments={"text": "Quarterly voicebot review"},
            is_consequential=False,
            is_idempotent=True,
            idempotency_key="idem-key-notes-001",
        )
        plan2 = WorkflowPlan(
            plan_id="plan-idem-2",
            session_id="session-idem",
            correlation_id="corr-idem",
            title="Second Call Plan",
            steps=[step2],
        )

        executor.start_workflow(plan2)
        # CRUCIAL ACCEPTANCE CRITERIA: Tool was NOT called a second time!
        assert call_count == 1
        assert step2.result == first_result
        assert step2.status == StepStatus.SUCCEEDED

        # Audit event records cache hit
        cache_events = [e for e in executor.audit_events if e.event_type == "workflow.idempotent_cache_hit"]
        assert len(cache_events) == 1
        assert cache_events[0].payload["idempotency_key"] == "idem-key-notes-001"


# ---------------------------------------------------------------------------
# 3. Step-Level Audit Trail & Progress Events (D17–18)
# ---------------------------------------------------------------------------

class TestAuditTrailAndProgressEvents:
    def test_step_level_audit_trail_and_progress_emission(self, harmless_registry):
        progress_records: List[Dict[str, Any]] = []

        def on_progress(data: Dict[str, Any]):
            progress_records.append(dict(data))

        executor = WorkflowExecutor(tool_registry=harmless_registry, on_progress=on_progress)
        plan = make_two_step_plan()

        res = executor.start_workflow(plan)
        assert res["status"] == "awaiting_approval"

        # Check progress events during wait
        assert len(progress_records) >= 1
        assert progress_records[-1]["completed_steps"] == 1
        assert progress_records[-1]["percent_complete"] == 50.0

        # Approve and finish
        req_id = res["approval_request"].request_id
        res2 = executor.approve_step(req_id)
        assert res2["status"] == "completed"

        # Check final progress event
        assert progress_records[-1]["percent_complete"] == 100.0
        assert progress_records[-1]["completed_steps"] == 2

        # Check audit trail contents
        event_types = [e.event_type for e in executor.audit_events]
        assert "workflow.initialized" in event_types
        assert "workflow.step_started" in event_types
        assert "workflow.step_completed" in event_types
        assert "workflow.approval_requested" in event_types
        assert "workflow.approval_granted" in event_types
        assert "workflow.progress" in event_types
        assert "workflow.completed" in event_types


# ---------------------------------------------------------------------------
# 4. Reasoning Proposals Integration (W3 -> W4) (D19–20)
# ---------------------------------------------------------------------------

class TestReasoningProposalIntegration:
    def test_proposal_adapter_creates_valid_dag_from_workflow_proposal(self, harmless_registry):
        proposal = WorkflowProposal(
            session_id="session-reasoning-01",
            correlation_id="corr-reasoning-01",
            intent="summarize_lecture_and_set_reminder",
            suggested_action="Format notes from CS101 lecture and schedule reminder for assignment",
            confidence=0.92,
            sources_used=[{"source_id": "frame_001", "uri": "synthetic://screen/frame_001"}],
        )

        plan = ReasoningProposalAdapter.proposal_to_plan(proposal)
        assert plan.session_id == "session-reasoning-01"
        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "format_notes"
        assert plan.steps[1].tool_name == "schedule_reminder"
        assert "step-1-format" in plan.steps[1].depends_on

        # Validate DAG safety through executor
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        execution_order = executor.validate_plan_safety(plan)
        assert execution_order == ["step-1-format", "step-2-reminder"]

    def test_proposal_adapter_ingests_w3_reasoning_result(self, harmless_registry):
        mock_reasoning_result = {
            "result_id": "res-uuid-123",
            "session_id": "session-w3-002",
            "correlation_id": "corr-w3-002",
            "response_text": "Grounded lecture summary on algorithms",
            "suggested_action": "Format notes and schedule reminder for lab exam",
            "confidence": 0.88,
            "sources_used": [{"source_id": "src_1", "snippet": "Exam scheduled on Friday"}],
        }

        plan = ReasoningProposalAdapter.reasoning_result_to_plan(mock_reasoning_result)
        assert plan.session_id == "session-w3-002"
        assert len(plan.steps) == 2

        executor = WorkflowExecutor(tool_registry=harmless_registry)
        res = executor.start_workflow(plan)
        assert res["status"] == "awaiting_approval"


# ---------------------------------------------------------------------------
# 5. Backend Approval State Bridge (W4 <-> W5) (D19–20)
# ---------------------------------------------------------------------------

class TestBackendApprovalBridge:
    def test_backend_bridge_synchronization_and_audit_export(self, harmless_registry):
        bridge = BackendApprovalBridge()
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        plan = make_two_step_plan()

        res = executor.start_workflow(plan)
        req: ApprovalRequest = res["approval_request"]

        # Register request in backend bridge
        bridge.register_approval_request(req)
        assert bridge.get_approval_state(req.request_id) == ApprovalStatus.PENDING

        # Publish all executor audit events to backend bridge
        for event in executor.audit_events:
            bridge.publish_audit_event(event)

        session_events = bridge.get_session_audit_trail(plan.session_id)
        assert len(session_events) == len(executor.audit_events)

        # Update backend approval state
        updated = bridge.update_backend_approval(
            request_id=req.request_id,
            status=ApprovalStatus.APPROVED,
            decided_by="admin_backend",
        )
        assert updated.status == ApprovalStatus.APPROVED
        assert bridge.get_approval_state(req.request_id) == ApprovalStatus.APPROVED


# ---------------------------------------------------------------------------
# 6. UI Controller & Duplicate / Expired Approval Security (D19–20)
# ---------------------------------------------------------------------------

class TestUIControllerAndApprovalGuarantees:
    def test_ui_controller_summary_and_approval_flow(self, harmless_registry):
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        ui = UIWorkflowController(executor=executor)
        plan = make_two_step_plan()

        executor.start_workflow(plan)
        summary = ui.get_ui_summary()

        assert summary["active"] is True
        assert summary["total_steps"] == 2
        assert summary["completed_steps"] == 1
        assert len(summary["pending_approvals"]) == 1

        req_id = summary["pending_approvals"][0]["request_id"]

        # User approves via UI
        ui_res = ui.submit_approval_decision(request_id=req_id, decision="approve", user_name="student_user")
        assert ui_res["status"] == "approved"
        assert ui_res["execution_result"]["status"] == "completed"

    def test_duplicate_approval_submission_is_strictly_blocked(self, harmless_registry):
        """CRUCIAL ACCEPTANCE CRITERIA: Duplicate approvals are blocked to prevent repeat execution."""
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        ui = UIWorkflowController(executor=executor)
        plan = make_two_step_plan()

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # First approval succeeds
        ui.submit_approval_decision(request_id=req_id, decision="approve", user_name="student_user")

        # Second approval attempt MUST raise DuplicateApprovalError
        with pytest.raises(DuplicateApprovalError):
            ui.submit_approval_decision(request_id=req_id, decision="approve", user_name="student_user")

    def test_expired_approval_strictly_guarantees_no_execution(self, harmless_registry):
        """CRUCIAL ACCEPTANCE CRITERIA: An expired approval guarantees no tool execution."""
        executor = WorkflowExecutor(tool_registry=harmless_registry, default_approval_ttl_seconds=0.01)
        plan = make_two_step_plan()

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # Simulating time passage past TTL
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        executor.check_and_expire_pending(now=future_time)

        # Attempting late approval must fail with ApprovalExpiredError
        with pytest.raises(ApprovalExpiredError):
            executor.approve_step(req_id)

        # Confirm step-2 was never executed
        assert plan.steps[1].result is None
        assert plan.steps[1].status == StepStatus.CANCELLED
        assert plan.state == WorkflowState.CANCELLED

    def test_ui_rejection_guarantees_no_tool_execution(self, harmless_registry):
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        ui = UIWorkflowController(executor=executor)
        plan = make_two_step_plan()

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # User rejects via UI
        ui_res = ui.submit_approval_decision(
            request_id=req_id,
            decision="reject",
            user_name="student_user",
            reason="Do not need a reminder",
        )
        assert ui_res["status"] == "rejected"
        assert plan.steps[1].result is None
        assert plan.steps[1].status == StepStatus.CANCELLED
        assert plan.state == WorkflowState.CANCELLED
