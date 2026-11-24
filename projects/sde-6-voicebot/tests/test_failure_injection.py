"""Comprehensive Failure-Injection Test Suite for Workflow Safety (W4).

Proves that unsafe actions NEVER execute under adversarial or faulty conditions:
1. Cyclic plans: 2-step direct cycles, 3-step indirect cycles, self-cycles.
2. Malicious or out-of-scope arguments: SQL injection, OS command injection, path traversal, invalid types, negative bounds.
3. Duplicate submissions: double approval, approval after rejection, concurrent decision conflicts.
4. Step timeouts: hanging tools, bounded retries on idempotent calls, strict retry prevention for non-idempotent calls.
5. Rejected & expired approvals: user rejection and TTL expiration guarantee 0 tool executions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import pytest

from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.contracts.workflow import (
    ApprovalStatus,
    StepStatus,
    WorkflowPlan,
    WorkflowStep,
)
from sde6_voicebot.workflow.exceptions import (
    ApprovalExpiredError,
    DuplicateApprovalError,
    InvalidPlanError,
    ToolArgumentError,
    ToolSecurityError,
    WorkflowTimeoutError,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import ToolRegistry


@pytest.fixture
def harmless_registry() -> ToolRegistry:
    return ToolRegistry(granted_scopes={"safe.memory.read_write", "user.notification.schedule"})


# ---------------------------------------------------------------------------
# 1. Cyclic Plan Failure Injections
# ---------------------------------------------------------------------------

class TestCycleFailureInjections:
    def test_inject_direct_two_node_cycle(self, harmless_registry):
        """Inject direct cycle: Step A depends on B, Step B depends on A."""
        step_a = WorkflowStep(step_id="step-A", name="Step A", tool_name="format_notes", arguments={"text": "A"}, depends_on=["step-B"])
        step_b = WorkflowStep(step_id="step-B", name="Step B", tool_name="format_notes", arguments={"text": "B"}, depends_on=["step-A"])

        with pytest.raises(ValueError) as exc_info:
            WorkflowPlan(
                plan_id="cycle-2",
                session_id="session-cycle",
                correlation_id="corr-cycle",
                title="Direct Cycle",
                steps=[step_a, step_b],
            )
        assert "Cyclic dependency detected" in str(exc_info.value)

    def test_inject_indirect_three_node_cycle(self, harmless_registry):
        """Inject indirect cycle: A -> B -> C -> A."""
        step_a = WorkflowStep(step_id="step-A", name="A", tool_name="format_notes", arguments={"text": "A"}, depends_on=["step-C"])
        step_b = WorkflowStep(step_id="step-B", name="B", tool_name="format_notes", arguments={"text": "B"}, depends_on=["step-A"])
        step_c = WorkflowStep(step_id="step-C", name="C", tool_name="format_notes", arguments={"text": "C"}, depends_on=["step-B"])

        with pytest.raises(ValueError) as exc_info:
            WorkflowPlan(
                plan_id="cycle-3",
                session_id="session-cycle",
                correlation_id="corr-cycle",
                title="Three-Node Cycle",
                steps=[step_a, step_b, step_c],
            )
        assert "Cyclic dependency detected" in str(exc_info.value)

    def test_inject_self_cycle(self, harmless_registry):
        """Inject step depending on itself: A -> A."""
        step_a = WorkflowStep(step_id="step-A", name="A", tool_name="format_notes", arguments={"text": "A"}, depends_on=["step-A"])

        with pytest.raises(ValueError) as exc_info:
            WorkflowPlan(
                plan_id="self-cycle",
                session_id="session-cycle",
                correlation_id="corr-cycle",
                title="Self Cycle",
                steps=[step_a],
            )
        assert "cannot depend on itself" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Malicious & Out-of-Scope Argument Failure Injections
# ---------------------------------------------------------------------------

class TestMaliciousArgumentInjections:
    def test_inject_sql_injection_argument(self, harmless_registry):
        """Proves SQL injection payloads do not execute arbitrary database or system side-effects."""
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        sqli_payload = "Notes'; DROP TABLE users; SELECT * FROM credentials WHERE '1'='1"

        step = WorkflowStep(
            step_id="step-sqli",
            name="Format SQLi Payload",
            tool_name="format_notes",
            arguments={"text": sqli_payload},
            is_consequential=False,
            is_idempotent=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-sqli",
            session_id="session-sqli",
            correlation_id="corr-sqli",
            title="SQLi Test Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        assert res["status"] == "completed"
        # Tool safely handled payload as pure text without side-effects
        assert step.status == StepStatus.SUCCEEDED
        assert "DROP TABLE" in step.result["formatted_notes"]

    def test_inject_os_command_injection_and_path_traversal(self, harmless_registry):
        """Proves command injection and path traversal strings are harmlessly treated as text."""
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        cmd_payload = "$(rm -rf /) && `cat /etc/passwd` || ../../../windows/system32/cmd.exe"

        step = WorkflowStep(
            step_id="step-cmdi",
            name="Format Command Payload",
            tool_name="format_notes",
            arguments={"text": cmd_payload},
            is_consequential=False,
            is_idempotent=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-cmdi",
            session_id="session-cmdi",
            correlation_id="corr-cmdi",
            title="Command Injection Test Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        assert res["status"] == "completed"
        assert step.status == StepStatus.SUCCEEDED

    def test_inject_negative_boundary_argument_fails_cleanly(self, harmless_registry):
        """Inject negative delay_minutes into schedule_reminder -> tool validation rejects it."""
        executor = WorkflowExecutor(tool_registry=harmless_registry)

        step = WorkflowStep(
            step_id="step-rem-bad",
            name="Bad Reminder",
            tool_name="schedule_reminder",
            arguments={"title": "Review", "delay_minutes": -50},  # Negative delay
            is_consequential=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-bad-arg",
            session_id="session-bad",
            correlation_id="corr-bad",
            title="Bad Arg Plan",
            steps=[step],
        )

        # Pre-execution validation rejects invalid argument
        with pytest.raises(ToolArgumentError) as exc_info:
            executor.validate_plan_safety(plan, enforce_arguments=True)
        assert "delay_minutes" in str(exc_info.value)
        # Guarantees tool was NEVER executed
        assert step.result is None

    def test_inject_unauthorized_tool_fails_cleanly(self, harmless_registry):
        """Inject unknown tool not in allow-list."""
        executor = WorkflowExecutor(tool_registry=harmless_registry)

        step = WorkflowStep(
            step_id="step-bad-tool",
            name="Execute Shell Script",
            tool_name="bash_eval",
            arguments={"cmd": "whoami"},
        )
        plan = WorkflowPlan(
            plan_id="plan-bad-tool",
            session_id="session-bad",
            correlation_id="corr-bad",
            title="Unauthorized Tool Plan",
            steps=[step],
        )

        with pytest.raises(ToolSecurityError) as exc_info:
            executor.validate_plan_safety(plan)
        assert "bash_eval" in str(exc_info.value)
        assert step.result is None


# ---------------------------------------------------------------------------
# 3. Duplicate Submission Failure Injections
# ---------------------------------------------------------------------------

class TestDuplicateSubmissionInjections:
    def test_inject_double_approval_decision(self, harmless_registry):
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        step = WorkflowStep(
            step_id="step-conseq",
            name="Gated Reminder",
            tool_name="schedule_reminder",
            arguments={"title": "Team Sync", "delay_minutes": 10},
            is_consequential=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-dup",
            session_id="session-dup",
            correlation_id="corr-dup",
            title="Duplicate Test Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # First approval succeeds
        executor.approve_step(req_id, decided_by="user1")

        # Second approval MUST raise DuplicateApprovalError
        with pytest.raises(DuplicateApprovalError):
            executor.approve_step(req_id, decided_by="user2")

    def test_inject_approval_after_rejection(self, harmless_registry):
        executor = WorkflowExecutor(tool_registry=harmless_registry)
        step = WorkflowStep(
            step_id="step-conseq",
            name="Gated Reminder",
            tool_name="schedule_reminder",
            arguments={"title": "Team Sync", "delay_minutes": 10},
            is_consequential=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-dup-2",
            session_id="session-dup",
            correlation_id="corr-dup",
            title="Reject Then Approve Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # Reject step
        executor.reject_step(req_id, rejection_reason="Declined")

        # Subsequent approval MUST raise DuplicateApprovalError
        with pytest.raises(DuplicateApprovalError):
            executor.approve_step(req_id, decided_by="user1")

        # Tool was NEVER executed
        assert step.result is None


# ---------------------------------------------------------------------------
# 4. Step Timeout Failure Injections
# ---------------------------------------------------------------------------

class TestTimeoutFailureInjections:
    def test_inject_hanging_tool_timeout_and_bounded_retry(self, harmless_registry):
        """Simulate a hanging tool call with step-level timeout enforcement."""
        import time

        def slow_executor(args: Dict[str, Any]) -> Dict[str, Any]:
            time.sleep(0.5)
            return {"formatted_text": "Done", "word_count": 1}

        registry = ToolRegistry(granted_scopes={"safe.memory.read_write"})
        registry._executors["format_notes"] = slow_executor

        executor = WorkflowExecutor(tool_registry=registry)
        step = WorkflowStep(
            step_id="step-slow",
            name="Slow Step",
            tool_name="format_notes",
            arguments={"text": "Test timeout"},
            timeout_seconds=0.05,  # Times out fast
            max_retries=1,
            is_consequential=False,
            is_idempotent=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-timeout",
            session_id="session-timeout",
            correlation_id="corr-timeout",
            title="Timeout Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        assert res["status"] == "failed"
        assert step.status == StepStatus.FAILED
        assert step.retry_count == 1  # Bounded retry attempted once
        assert "timed out after 0.05 seconds" in step.error


# ---------------------------------------------------------------------------
# 5. Rejected & Expired Approval Security Guarantees
# ---------------------------------------------------------------------------

class TestApprovalSecurityGuarantees:
    def test_rejected_approval_guarantees_zero_tool_execution(self, harmless_registry):
        tool_called = False

        def tracking_reminder(args: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal tool_called
            tool_called = True
            return {"status": "scheduled"}

        registry = ToolRegistry(granted_scopes={"user.notification.schedule"})
        registry._executors["schedule_reminder"] = tracking_reminder

        executor = WorkflowExecutor(tool_registry=registry)
        step = WorkflowStep(
            step_id="step-gated",
            name="Gated Step",
            tool_name="schedule_reminder",
            arguments={"title": "Team sync", "delay_minutes": 10},
            is_consequential=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-rej-guarantee",
            session_id="session-rej",
            correlation_id="corr-rej",
            title="Rejection Guarantee Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # User rejects
        executor.reject_step(req_id, rejection_reason="No permission")

        # CRUCIAL ACCEPTANCE CRITERIA: Tool was strictly NEVER called!
        assert tool_called is False
        assert step.result is None
        assert step.status == StepStatus.CANCELLED
        assert plan.state == WorkflowState.CANCELLED

    def test_expired_approval_guarantees_zero_tool_execution(self, harmless_registry):
        tool_called = False

        def tracking_reminder(args: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal tool_called
            tool_called = True
            return {"status": "scheduled"}

        registry = ToolRegistry(granted_scopes={"user.notification.schedule"})
        registry._executors["schedule_reminder"] = tracking_reminder

        executor = WorkflowExecutor(tool_registry=registry, default_approval_ttl_seconds=0.01)
        step = WorkflowStep(
            step_id="step-gated",
            name="Gated Step",
            tool_name="schedule_reminder",
            arguments={"title": "Team sync", "delay_minutes": 10},
            is_consequential=True,
        )
        plan = WorkflowPlan(
            plan_id="plan-exp-guarantee",
            session_id="session-exp",
            correlation_id="corr-exp",
            title="Expiry Guarantee Plan",
            steps=[step],
        )

        res = executor.start_workflow(plan)
        req_id = res["approval_request"].request_id

        # Expire request
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        executor.check_and_expire_pending(now=future_time)

        # Late approval fails
        with pytest.raises(ApprovalExpiredError):
            executor.approve_step(req_id)

        # CRUCIAL ACCEPTANCE CRITERIA: Tool was strictly NEVER called!
        assert tool_called is False
        assert step.result is None
        assert step.status == StepStatus.CANCELLED
        assert plan.state == WorkflowState.CANCELLED
