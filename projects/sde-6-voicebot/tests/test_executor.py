"""Integration tests for WorkflowExecutor, approval gating, and safety guarantees."""

import pytest

from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.contracts.workflow import (
    ApprovalStatus,
    StepStatus,
    WorkflowPlan,
    WorkflowStep,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor


def test_harmless_step_runs_without_approval():
    """Non-consequential step executes directly through to SUCCEEDED."""
    step = WorkflowStep(
        step_id="step-notes",
        name="Format Quick Notes",
        tool_name="format_notes",
        arguments={"text": "First point\nSecond point"},
        is_consequential=False,
    )
    plan = WorkflowPlan(
        session_id="sess-auto",
        correlation_id="corr-auto",
        title="Auto Safe Workflow",
        steps=[step],
    )

    executor = WorkflowExecutor()
    res = executor.start_workflow(plan)

    assert res["status"] == "completed"
    assert res["result"].final_state == WorkflowState.SUCCEEDED
    assert step.step_id in res["result"].completed_steps
    assert "formatted_notes" in res["result"].step_results[step.step_id]


def test_consequential_action_defaults_to_awaiting_approval():
    """Consequential action defaults to awaiting approval and halts execution."""
    step = WorkflowStep(
        step_id="step-remind",
        name="Schedule Alert",
        tool_name="schedule_reminder",
        arguments={"title": "Team Standup", "delay_minutes": 10},
        is_consequential=True,  # Consequential action
    )
    plan = WorkflowPlan(
        session_id="sess-gate",
        correlation_id="corr-gate",
        title="Gated Workflow",
        steps=[step],
    )

    executor = WorkflowExecutor()
    outcome = executor.start_workflow(plan)

    assert outcome["status"] == "awaiting_approval"
    assert executor.current_state == WorkflowState.AWAITING_APPROVAL
    assert step.status == StepStatus.AWAITING_APPROVAL
    assert len(executor.pending_approvals) == 1

    req_id = list(executor.pending_approvals.keys())[0]
    req = executor.pending_approvals[req_id]
    assert req.tool_name == "schedule_reminder"
    assert req.status == ApprovalStatus.PENDING


def test_approved_consequential_action_executes_successfully():
    """When approved, the consequential action resumes and executes to completion."""
    step = WorkflowStep(
        step_id="step-remind",
        name="Schedule Alert",
        tool_name="schedule_reminder",
        arguments={"title": "Demo rehearsal", "delay_minutes": 20},
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-approve",
        correlation_id="corr-approve",
        title="Approved Workflow",
        steps=[step],
    )

    executor = WorkflowExecutor()
    outcome = executor.start_workflow(plan)
    assert outcome["status"] == "awaiting_approval"

    req_id = outcome["approval_request"].request_id
    res = executor.approve_step(req_id, decided_by="lead_reviewer")

    assert res["status"] == "completed"
    assert res["result"].final_state == WorkflowState.SUCCEEDED
    assert executor.current_state == WorkflowState.SUCCEEDED
    assert step.result["status"] == "scheduled"
    assert step.result["title"] == "Demo rehearsal"


def test_rejected_consequential_action_guarantees_no_execution():
    """When rejected, tool is NEVER executed, and workflow ends in CANCELLED state."""
    step = WorkflowStep(
        step_id="step-remind",
        name="Schedule Risky Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "Risky Event", "delay_minutes": 5},
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-reject",
        correlation_id="corr-reject",
        title="Rejected Workflow",
        steps=[step],
    )

    executor = WorkflowExecutor()
    outcome = executor.start_workflow(plan)
    req_id = outcome["approval_request"].request_id

    result = executor.reject_step(req_id, rejection_reason="Declined by user", decided_by="operator")

    assert result.final_state == WorkflowState.CANCELLED
    assert executor.current_state == WorkflowState.CANCELLED
    assert step.status == StepStatus.CANCELLED
    assert step.result is None  # Tool was NEVER executed!
    assert "Declined by user" in step.error

    # Verify safe audit event was recorded
    rejection_events = [e for e in result.audit_events if e.event_type == "workflow.approval_rejected"]
    assert len(rejection_events) == 1
    assert rejection_events[0].payload["tool_executed"] is False


def test_multi_step_dependency_chain_with_approval_gate():
    """Multi-step plan: Step 1 (safe) -> Step 2 (consequential).
    Step 1 executes immediately; Step 2 pauses for approval, then completes once approved.
    """
    step1 = WorkflowStep(
        step_id="step-1",
        name="Format Notes",
        tool_name="format_notes",
        arguments={"text": "Action items from sprint planning"},
        is_consequential=False,
    )
    step2 = WorkflowStep(
        step_id="step-2",
        name="Set Sprint Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "Sprint retrospective", "delay_minutes": 60},
        depends_on=["step-1"],
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-multi",
        correlation_id="corr-multi",
        title="Two-Step Pipeline",
        steps=[step1, step2],
    )

    executor = WorkflowExecutor()
    outcome = executor.start_workflow(plan)

    # Step 1 should have succeeded, and Step 2 should be awaiting approval
    assert step1.status == StepStatus.SUCCEEDED
    assert outcome["status"] == "awaiting_approval"
    assert outcome["step_id"] == "step-2"

    req_id = outcome["approval_request"].request_id
    res = executor.approve_step(req_id)

    assert res["status"] == "completed"
    assert res["result"].final_state == WorkflowState.SUCCEEDED
    assert step2.status == StepStatus.SUCCEEDED
    assert len(res["result"].completed_steps) == 2


def test_step_failure_triggers_workflow_failed_state():
    """Step execution failure transitions workflow state to FAILED."""
    bad_step = WorkflowStep(
        step_id="step-fail",
        name="Bad Format Call",
        tool_name="format_notes",
        arguments={"text": ""},  # Invalid empty text triggers ToolExecutionError
        is_consequential=False,
    )
    plan = WorkflowPlan(
        session_id="sess-err",
        correlation_id="corr-err",
        title="Failing Plan",
        steps=[bad_step],
    )

    executor = WorkflowExecutor()
    res = executor.start_workflow(plan)

    assert res["status"] == "failed"
    assert res["result"].final_state == WorkflowState.FAILED
    assert executor.current_state == WorkflowState.FAILED
    assert bad_step.status == StepStatus.FAILED
    assert res["result"].error is not None
    assert res["result"].error.code == "WORKFLOW_FAILED"
