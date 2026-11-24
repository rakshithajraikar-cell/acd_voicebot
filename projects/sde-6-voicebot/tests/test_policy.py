"""Policy, validation, approval, timeout, retry, and cancellation test suite (Week 2 / Days 8–14).

Acceptance Criteria:
- Plans with cycles or missing dependencies are rejected with clear errors.
- Unknown tools and invalid arguments are rejected; permission scopes are enforced.
- A rejected or expired approval guarantees no tool execution and records a safe audit event.
- Executor enforces timeouts; retries are bounded and only for idempotent calls; cancellation works.
- Only harmless mock tools exist; no external sending or computer control.
- No duplicate schemas; tests pass in mock mode.
"""

from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict
import pytest

from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.contracts.workflow import (
    ApprovalRequest,
    ApprovalStatus,
    StepStatus,
    ToolSpec,
    WorkflowPlan,
    WorkflowStep,
)
from sde6_voicebot.workflow.exceptions import (
    ApprovalExpiredError,
    InvalidPlanError,
    PermissionScopeError,
    ToolArgumentError,
    ToolExecutionError,
    ToolSecurityError,
    WorkflowCancelledError,
    WorkflowTimeoutError,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import (
    FORMAT_NOTES_SPEC,
    SCHEDULE_REMINDER_SPEC,
    SCOPE_MEMORY_RW,
    SCOPE_NOTIFICATION_SCHEDULE,
    ToolRegistry,
)
from sde6_voicebot.workflow.validator import PlanValidator


# ============================================================================
# 1. PLAN VALIDATION TESTS: Dependencies & Cycle Detection
# ============================================================================

def test_plan_validator_accepts_valid_dag():
    """PlanValidator verifies an acyclic multi-step dependency graph."""
    s1 = WorkflowStep(step_id="step-1", name="Step 1", tool_name="format_notes", arguments={"text": "Hello"})
    s2 = WorkflowStep(step_id="step-2", name="Step 2", tool_name="format_notes", arguments={"text": "World"}, depends_on=["step-1"])
    plan = WorkflowPlan(session_id="s1", correlation_id="c1", title="DAG Plan", steps=[s1, s2])

    order = PlanValidator.validate(plan)
    assert order == ["step-1", "step-2"]


def test_plan_validator_rejects_missing_dependency():
    """Plan with missing dependency is rejected with a clear, descriptive error."""
    s1 = WorkflowStep(
        step_id="step-1",
        name="Step 1",
        tool_name="format_notes",
        arguments={"text": "Hello"},
        depends_on=["non_existent_step_404"],
    )
    # The Pydantic model itself validates referential integrity
    with pytest.raises(ValueError, match="depends on non-existent step 'non_existent_step_404'"):
        WorkflowPlan(session_id="s1", correlation_id="c1", title="Missing Dep", steps=[s1])


def test_plan_validator_rejects_cycles_with_details():
    """Plan with cyclic dependencies is detected and rejected with cyclic step IDs."""
    s1 = WorkflowStep(step_id="s1", name="S1", tool_name="format_notes", arguments={"text": "A"}, depends_on=["s2"])
    s2 = WorkflowStep(step_id="s2", name="S2", tool_name="format_notes", arguments={"text": "B"}, depends_on=["s1"])

    with pytest.raises(ValueError, match="Cyclic dependency detected among steps: \\['s1', 's2'\\]"):
        WorkflowPlan(session_id="sess", correlation_id="corr", title="Cycle Plan", steps=[s1, s2])


# ============================================================================
# 2. TOOL REGISTRY, ALLOW-LIST, ARGUMENT VALIDATION & PERMISSION SCOPES
# ============================================================================

def test_registry_contains_strictly_only_harmless_mock_tools():
    """Safety acceptance: Only the allow-listed mock tools exist. No computer control or external send."""
    registry = ToolRegistry()
    allowed = registry.list_specs()
    assert set(allowed.keys()) == {"format_notes", "schedule_reminder"}
    for name, spec in allowed.items():
        assert "exec" not in name
        assert "shell" not in name
        assert "socket" not in name
        assert spec.permission_scope in {SCOPE_MEMORY_RW, SCOPE_NOTIFICATION_SCHEDULE}


def test_registry_blocks_unknown_tools():
    """Execution or registration of unknown tools raises ToolSecurityError."""
    registry = ToolRegistry()
    with pytest.raises(ToolSecurityError, match="Unauthorized tool 'shell_exec'"):
        registry.get_spec("shell_exec")

    with pytest.raises(ToolSecurityError, match="Security violation: Attempted execution of unapproved tool 'send_email'"):
        registry.execute_tool("send_email", {"to": "test@example.com"})


def test_argument_validation_for_format_notes():
    """Argument validator rejects missing, non-string, or invalid bullet_style parameters."""
    registry = ToolRegistry()

    # Missing required argument
    with pytest.raises(ToolArgumentError, match="Missing required argument 'text'"):
        registry.validate_arguments("format_notes", {})

    # Blank/empty string
    with pytest.raises(ToolArgumentError, match="Argument 'text' must be a non-empty string"):
        registry.validate_arguments("format_notes", {"text": "   "})

    # Invalid bullet_style
    with pytest.raises(ToolArgumentError, match="Argument 'bullet_style' must be one of"):
        registry.validate_arguments("format_notes", {"text": "Notes", "bullet_style": "circle"})


def test_argument_validation_for_schedule_reminder():
    """Argument validator rejects invalid delay_minutes and invalid priority values."""
    registry = ToolRegistry()

    # Missing title
    with pytest.raises(ToolArgumentError, match="Missing required argument 'title'"):
        registry.validate_arguments("schedule_reminder", {"delay_minutes": 10})

    # Non-positive or boolean delay
    with pytest.raises(ToolArgumentError, match="Argument 'delay_minutes' must be a positive integer"):
        registry.validate_arguments("schedule_reminder", {"title": "Team sync", "delay_minutes": 0})

    with pytest.raises(ToolArgumentError, match="Argument 'delay_minutes' must be a positive integer"):
        registry.validate_arguments("schedule_reminder", {"title": "Team sync", "delay_minutes": -5})

    with pytest.raises(ToolArgumentError, match="Argument 'delay_minutes' must be a positive integer"):
        registry.validate_arguments("schedule_reminder", {"title": "Team sync", "delay_minutes": True})

    # Invalid priority enum
    with pytest.raises(ToolArgumentError, match="Argument 'priority' must be one of"):
        registry.validate_arguments("schedule_reminder", {"title": "Sync", "delay_minutes": 5, "priority": "critical"})


def test_permission_scope_enforcement():
    """Permission scope enforcement blocks execution if caller lacks required scope."""
    # Registry configured with only memory scope (missing notification scope)
    restricted_registry = ToolRegistry(granted_scopes={SCOPE_MEMORY_RW})

    # format_notes requires SCOPE_MEMORY_RW -> succeeds
    res = restricted_registry.execute_tool("format_notes", {"text": "Safe text"})
    assert res["status"] == "success"

    # schedule_reminder requires SCOPE_NOTIFICATION_SCHEDULE -> blocked with PermissionScopeError
    with pytest.raises(PermissionScopeError) as exc_info:
        restricted_registry.execute_tool("schedule_reminder", {"title": "Alert", "delay_minutes": 10})

    assert exc_info.value.required_scope == SCOPE_NOTIFICATION_SCHEDULE
    assert "Permission denied: Tool 'schedule_reminder' requires permission scope" in str(exc_info.value)


# ============================================================================
# 3. APPROVAL LOGIC: REJECTION & EXPIRY GUARANTEES
# ============================================================================

def test_rejection_guarantees_no_tool_execution_and_records_audit():
    """A rejected approval strictly guarantees no tool execution and emits workflow.approval_rejected."""
    consequential_step = WorkflowStep(
        step_id="step-risky-1",
        name="Consequential Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "High Impact", "delay_minutes": 15},
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-rej-test",
        correlation_id="corr-rej-test",
        title="Rejection Guarantee Plan",
        steps=[consequential_step],
    )

    executor = WorkflowExecutor()
    gate_res = executor.start_workflow(plan)
    assert gate_res["status"] == "awaiting_approval"
    req_id = gate_res["approval_request"].request_id

    # Reject the request
    result = executor.reject_step(req_id, rejection_reason="Declined by user security policy", decided_by="qa_tester")

    # Invariants
    assert result.final_state == WorkflowState.CANCELLED
    assert executor.current_state == WorkflowState.CANCELLED
    assert consequential_step.status == StepStatus.CANCELLED
    assert consequential_step.result is None  # TOOL NEVER RAN!
    assert "Declined by user security policy" in consequential_step.error

    # Audit event verification
    rej_events = [e for e in result.audit_events if e.event_type == "workflow.approval_rejected"]
    assert len(rej_events) == 1
    assert rej_events[0].payload["tool_executed"] is False
    assert rej_events[0].payload["decided_by"] == "qa_tester"


def test_expired_approval_guarantees_no_tool_execution():
    """An expired approval strictly guarantees no tool execution and emits workflow.approval_expired."""
    consequential_step = WorkflowStep(
        step_id="step-expire-1",
        name="Timed Out Action",
        tool_name="schedule_reminder",
        arguments={"title": "Urgent Action", "delay_minutes": 10},
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-exp-test",
        correlation_id="corr-exp-test",
        title="Expiry Guarantee Plan",
        steps=[consequential_step],
    )

    # Short default TTL
    executor = WorkflowExecutor(default_approval_ttl_seconds=0.01)
    gate_res = executor.start_workflow(plan)
    assert gate_res["status"] == "awaiting_approval"
    req_id = gate_res["approval_request"].request_id

    # Wait for TTL to elapse
    time.sleep(0.05)

    # Attempting to approve an expired request raises ApprovalExpiredError
    with pytest.raises(ApprovalExpiredError, match="expired"):
        executor.approve_step(req_id, decided_by="late_reviewer")

    # Invariants: tool NEVER executed
    assert consequential_step.result is None
    assert consequential_step.status == StepStatus.CANCELLED
    assert executor.current_state == WorkflowState.CANCELLED

    # Check audit events for expiry
    exp_events = [e for e in executor.audit_events if e.event_type == "workflow.approval_expired"]
    assert len(exp_events) == 1
    assert exp_events[0].payload["tool_executed"] is False


def test_explicit_expire_step_cancels_workflow():
    """Explicit expiration transitions workflow to CANCELLED and halts execution."""
    step = WorkflowStep(
        step_id="step-exp-2",
        name="Explicit Expiry Action",
        tool_name="schedule_reminder",
        arguments={"title": "Action", "delay_minutes": 20},
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-exp-2",
        correlation_id="corr-exp-2",
        title="Explicit Expiry Plan",
        steps=[step],
    )

    executor = WorkflowExecutor()
    gate_res = executor.start_workflow(plan)
    req_id = gate_res["approval_request"].request_id

    result = executor.expire_step(req_id, reason="Timeout exceeded by supervisor")
    assert result.final_state == WorkflowState.CANCELLED
    assert step.result is None
    assert step.status == StepStatus.CANCELLED

    audit_types = [e.event_type for e in result.audit_events]
    assert "workflow.approval_expired" in audit_types


# ============================================================================
# 4. EXECUTOR TIMEOUTS, BOUNDED RETRIES & CANCELLATION
# ============================================================================

def test_executor_enforces_step_timeout(monkeypatch):
    """Step execution exceeding timeout_seconds is terminated with WorkflowTimeoutError."""
    # Monkeypatch format_notes executor to simulate a slow / hanging operation
    def slow_format_notes(args):
        time.sleep(0.2)
        return {"status": "success"}

    registry = ToolRegistry()
    monkeypatch.setitem(registry._executors, "format_notes", slow_format_notes)

    step = WorkflowStep(
        step_id="step-slow",
        name="Slow Step",
        tool_name="format_notes",
        arguments={"text": "Test timeout"},
        timeout_seconds=0.05,  # Very short timeout
        is_consequential=False,
        max_retries=0,
    )
    plan = WorkflowPlan(
        session_id="sess-timeout",
        correlation_id="corr-timeout",
        title="Timeout Plan",
        steps=[step],
    )

    executor = WorkflowExecutor(tool_registry=registry)
    res = executor.start_workflow(plan)

    assert res["status"] == "failed"
    assert res["result"].final_state == WorkflowState.FAILED
    assert step.status == StepStatus.FAILED
    assert "timed out after 0.05 seconds" in step.error

    # Verify timeout audit event
    timeout_events = [e for e in res["result"].audit_events if e.event_type == "workflow.step_timeout"]
    assert len(timeout_events) == 1
    assert timeout_events[0].payload["timeout_seconds"] == 0.05


def test_bounded_retries_for_idempotent_step(monkeypatch):
    """Idempotent step retries on failure up to max_retries, succeeding on attempt 2."""
    call_attempts = {"count": 0}

    def flaky_format_notes(args):
        call_attempts["count"] += 1
        if call_attempts["count"] < 2:
            raise ToolExecutionError("Transient mock service glitch", tool_name="format_notes")
        return {"status": "success", "formatted_notes": "- Flaky notes"}

    registry = ToolRegistry()
    monkeypatch.setitem(registry._executors, "format_notes", flaky_format_notes)

    step = WorkflowStep(
        step_id="step-retry-idemp",
        name="Idempotent Flaky Step",
        tool_name="format_notes",
        arguments={"text": "Flaky notes"},
        is_consequential=False,
        is_idempotent=True,  # Idempotent
        max_retries=2,       # Bounded retries
    )
    plan = WorkflowPlan(
        session_id="sess-retry",
        correlation_id="corr-retry",
        title="Retry Success Plan",
        steps=[step],
    )

    executor = WorkflowExecutor(tool_registry=registry)
    res = executor.start_workflow(plan)

    assert res["status"] == "completed"
    assert res["result"].final_state == WorkflowState.SUCCEEDED
    assert step.status == StepStatus.SUCCEEDED
    assert step.retry_count == 1
    assert call_attempts["count"] == 2

    retry_events = [e for e in res["result"].audit_events if e.event_type == "workflow.step_retry"]
    assert len(retry_events) == 1
    assert retry_events[0].payload["attempt"] == 1


def test_retries_strictly_blocked_for_non_idempotent_call(monkeypatch):
    """Non-idempotent call MUST NEVER be retried, failing immediately on first error."""
    call_attempts = {"count": 0}

    def failing_reminder(args):
        call_attempts["count"] += 1
        raise ToolExecutionError("Notification backend down", tool_name="schedule_reminder")

    registry = ToolRegistry()
    monkeypatch.setitem(registry._executors, "schedule_reminder", failing_reminder)

    # Consequential, non-idempotent step with max_retries configured
    step = WorkflowStep(
        step_id="step-no-retry",
        name="Non Idempotent Action",
        tool_name="schedule_reminder",
        arguments={"title": "Important reminder", "delay_minutes": 10},
        is_consequential=True,
        is_idempotent=False,  # NOT idempotent!
        max_retries=3,        # Even if set to 3, must be ignored!
    )
    plan = WorkflowPlan(
        session_id="sess-non-idemp",
        correlation_id="corr-non-idemp",
        title="Non-Idempotent Failure Plan",
        steps=[step],
    )

    executor = WorkflowExecutor(tool_registry=registry)
    gate = executor.start_workflow(plan)
    assert gate["status"] == "awaiting_approval"

    # User approves
    res = executor.approve_step(gate["approval_request"].request_id)

    assert res["status"] == "failed"
    assert res["result"].final_state == WorkflowState.FAILED
    assert step.status == StepStatus.FAILED
    # Crucial safety check: Only attempted ONCE; retries were strictly blocked
    assert call_attempts["count"] == 1
    assert step.retry_count == 0

    retry_events = [e for e in res["result"].audit_events if e.event_type == "workflow.step_retry"]
    assert len(retry_events) == 0  # No retry events emitted!


def test_workflow_cancellation():
    """Workflow cancellation halts all running/pending steps and transitions state to CANCELLED."""
    step1 = WorkflowStep(
        step_id="step-1",
        name="Step 1 Notes",
        tool_name="format_notes",
        arguments={"text": "Step 1 text"},
        is_consequential=False,
    )
    step2 = WorkflowStep(
        step_id="step-2",
        name="Step 2 Gated",
        tool_name="schedule_reminder",
        arguments={"title": "Step 2 reminder", "delay_minutes": 10},
        depends_on=["step-1"],
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-cancel",
        correlation_id="corr-cancel",
        title="Cancellation Plan",
        steps=[step1, step2],
    )

    executor = WorkflowExecutor()
    gate = executor.start_workflow(plan)
    assert gate["status"] == "awaiting_approval"
    assert executor.current_state == WorkflowState.AWAITING_APPROVAL

    # Explicit user cancellation
    result = executor.cancel_workflow(reason="User changed their mind")

    assert result.final_state == WorkflowState.CANCELLED
    assert executor.current_state == WorkflowState.CANCELLED
    assert step2.status == StepStatus.CANCELLED
    assert "User changed their mind" in step2.error
    assert len(executor.pending_approvals) == 0

    cancel_events = [e for e in result.audit_events if e.event_type == "workflow.cancelled"]
    assert len(cancel_events) == 1
    assert cancel_events[0].payload["reason"] == "User changed their mind"

    # Re-cancelling a terminated workflow raises WorkflowCancelledError
    with pytest.raises(WorkflowCancelledError):
        executor.cancel_workflow()
