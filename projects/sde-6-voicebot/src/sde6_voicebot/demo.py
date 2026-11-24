"""Week 2 (Days 8–14) Runnable Demonstration Script for W4 Agentic Workflow.

Demonstrates:
1. Plan Validation:
   - Dependency cycle detection & diagnostic reporting
   - Missing/non-existent dependency rejection
   - Non-allowlisted tool blocking
   - Argument validation & constraint enforcement
   - Permission scope verification & rejection
2. Approved Plan Execution:
   - Safe step runs immediately -> consequential step pauses for approval -> approved -> completes
3. Rejected Plan Guarantee:
   - User declines approval -> tool NEVER executes (result is None) -> safe audit event emitted
4. Expired Approval Guarantee:
   - Approval TTL elapses -> tool NEVER executes -> safe audit event emitted
5. Executor Timeouts & Bounded Retries:
   - Idempotent tool transient failure bounded retry & recovery
6. Workflow Cancellation:
   - User cancellation halts all steps and cleans up pending approvals
7. Immutable Audit Event Trail (EventEnvelope):
   - Structured audit events tracking the entire lifecycle
"""

import json
import sys
import time
from pathlib import Path

# Ensure src directory is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.contracts.workflow import WorkflowPlan, WorkflowStep
from sde6_voicebot.workflow.exceptions import (
    ApprovalExpiredError,
    PermissionScopeError,
    ToolArgumentError,
    ToolExecutionError,
    ToolSecurityError,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import (
    SCOPE_MEMORY_RW,
    SCOPE_NOTIFICATION_SCHEDULE,
    ToolRegistry,
)
from sde6_voicebot.workflow.validator import PlanValidator


def banner(title: str) -> None:
    print("\n" + "=" * 75)
    print(f"  {title.upper()}")
    print("=" * 75)


def run_demo():
    banner("Academiaai AI Voicebot - SDE 6 (W4 Agentic Workflow Week 2 Demo)")
    print("Author: Spoorthi Y D (W4 Agentic Workflow Owner, SDE 6)")
    print("Mode: Mock Mode (Strict Allow-list, No External Calls, Safe Gated Execution)")

    # -------------------------------------------------------------------------
    # SCENARIO 1: PLAN VALIDATION, CYCLES, ARGUMENTS & PERMISSION SCOPES
    # -------------------------------------------------------------------------
    banner("Scenario 1: Plan Validation, Cycles, Arguments & Permission Scopes")

    print("1a. Testing Cyclic Dependency Detection (A -> B -> A)...")
    try:
        step_a = WorkflowStep(step_id="step-a", name="A", tool_name="format_notes", arguments={"text": "A"}, depends_on=["step-b"], is_consequential=False)
        step_b = WorkflowStep(step_id="step-b", name="B", tool_name="format_notes", arguments={"text": "B"}, depends_on=["step-a"], is_consequential=False)
        WorkflowPlan(session_id="s1", correlation_id="c1", title="Cycle Plan", steps=[step_a, step_b])
    except Exception as e:
        print(f"  [PASSED] Cycle rejected by validator: {e}")

    print("\n1b. Testing Missing Dependency Rejection (Depends on 'ghost-step')...")
    try:
        s_orphan = WorkflowStep(step_id="s1", name="Orphan", tool_name="format_notes", arguments={"text": "Txt"}, depends_on=["ghost-step"])
        WorkflowPlan(session_id="s1", correlation_id="c1", title="Orphan Plan", steps=[s_orphan])
    except Exception as e:
        print(f"  [PASSED] Missing dependency rejected: {e}")

    print("\n1c. Testing Disallowed Tool Blocking ('exec_shell')...")
    try:
        registry = ToolRegistry()
        registry.get_spec("exec_shell")
    except ToolSecurityError as e:
        print(f"  [PASSED] Non-allowlisted tool blocked: {e}")

    print("\n1d. Testing Tool Argument Validation (Empty text & negative delay)...")
    registry = ToolRegistry()
    try:
        registry.validate_arguments("format_notes", {"text": "   "})
    except ToolArgumentError as e:
        print(f"  [PASSED] Invalid text rejected: {e}")

    try:
        registry.validate_arguments("schedule_reminder", {"title": "Task", "delay_minutes": -10})
    except ToolArgumentError as e:
        print(f"  [PASSED] Negative delay rejected: {e}")

    print("\n1e. Testing Permission Scope Enforcement (Restricted caller)...")
    restricted_reg = ToolRegistry(granted_scopes={SCOPE_MEMORY_RW})
    try:
        restricted_reg.execute_tool("schedule_reminder", {"title": "Denied", "delay_minutes": 5})
    except PermissionScopeError as e:
        print(f"  [PASSED] Scope enforcement blocked execution: {e}")

    # -------------------------------------------------------------------------
    # SCENARIO 2: APPROVED PLAN FLOW (DEMO OF APPROVED PLAN)
    # -------------------------------------------------------------------------
    banner("Scenario 2: Approved Plan Execution Flow")
    s1 = WorkflowStep(
        step_id="step-1-notes",
        name="Format Meeting Notes",
        tool_name="format_notes",
        arguments={"text": "Finalize Q4 roadmap\nConduct architecture review", "bullet_style": "dash"},
        is_consequential=False,
    )
    s2 = WorkflowStep(
        step_id="step-2-alert",
        name="Schedule Team Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "Team Roadmap Sync", "delay_minutes": 30, "priority": "high"},
        depends_on=["step-1-notes"],
        is_consequential=True,
    )
    plan_approved = WorkflowPlan(
        session_id="sess-approved-101",
        correlation_id="corr-approved-101",
        title="Voice Notes & Reminder (Approved Flow)",
        steps=[s1, s2],
    )

    executor_app = WorkflowExecutor()
    print("Initiating plan execution...")
    gate_out = executor_app.start_workflow(plan_approved)

    print(f"Step 1 ('{s1.step_id}') finished: status={s1.status.value}")
    print(f"Step 2 ('{s2.step_id}') paused at gate: status={s2.status.value}")
    print(f"Engine State: {executor_app.current_state.value}")

    req_id = gate_out["approval_request"].request_id
    print(f"\nUser explicitly approves Request ID: {req_id}...")
    final_out = executor_app.approve_step(req_id, decided_by="spoorthi_lead")

    print(f"Pipeline Final State: {final_out['result'].final_state.value}")
    print(f"Completed Steps: {final_out['result'].completed_steps}")
    print("Step 1 Results:")
    print(json.dumps(final_out['result'].step_results["step-1-notes"], indent=2))
    print("Step 2 Results:")
    print(json.dumps(final_out['result'].step_results["step-2-alert"], indent=2))

    # -------------------------------------------------------------------------
    # SCENARIO 3: REJECTED PLAN FLOW (DEMO OF REJECTED PLAN)
    # -------------------------------------------------------------------------
    banner("Scenario 3: Rejected Plan Execution Flow (Rejection Guarantee)")
    s_reject = WorkflowStep(
        step_id="step-remind-reject",
        name="Broadcast Announcement",
        tool_name="schedule_reminder",
        arguments={"title": "Broadcast Alert", "delay_minutes": 10, "priority": "high"},
        is_consequential=True,
    )
    plan_reject = WorkflowPlan(
        session_id="sess-rej-202",
        correlation_id="corr-rej-202",
        title="Broadcast Workflow (Rejected Flow)",
        steps=[s_reject],
    )

    executor_rej = WorkflowExecutor()
    print(f"Starting consequential workflow '{plan_reject.title}'...")
    gate_rej = executor_rej.start_workflow(plan_reject)
    req_rej_id = gate_rej["approval_request"].request_id
    print(f"Workflow State: {executor_rej.current_state.value} (Awaiting approval)")

    print("\nSimulating user rejection decision: 'Operator denied permission'...")
    res_rejected = executor_rej.reject_step(
        req_rej_id,
        rejection_reason="Declined by operator: unauthorized external alert",
        decided_by="spoorthi_admin",
    )

    print(f"Final Workflow State: {res_rejected.final_state.value}")
    print(f"Step Result (guaranteed None - tool NEVER executed): {s_reject.result}")
    print(f"Step Status: {s_reject.status.value}")
    print(f"Step Error Log: {s_reject.error}")

    rej_event = [e for e in res_rejected.audit_events if e.event_type == "workflow.approval_rejected"][0]
    print(f"Audit Log Verified: event_type={rej_event.event_type}, tool_executed={rej_event.payload['tool_executed']}")

    # -------------------------------------------------------------------------
    # SCENARIO 4: EXPIRED APPROVAL FLOW (EXPIRY GUARANTEE)
    # -------------------------------------------------------------------------
    banner("Scenario 4: Expired Approval Flow (Expiry Guarantee)")
    s_expire = WorkflowStep(
        step_id="step-expire",
        name="Time Sensitive Action",
        tool_name="schedule_reminder",
        arguments={"title": "Time-sensitive sync", "delay_minutes": 5},
        is_consequential=True,
    )
    plan_expire = WorkflowPlan(
        session_id="sess-exp-303",
        correlation_id="corr-exp-303",
        title="Expiry Plan",
        steps=[s_expire],
    )

    # Set very short TTL (0.01 seconds) to simulate timeout
    executor_exp = WorkflowExecutor(default_approval_ttl_seconds=0.01)
    gate_exp = executor_exp.start_workflow(plan_expire)
    req_exp_id = gate_exp["approval_request"].request_id

    print(f"Approval Request created with TTL. Waiting for expiration...")
    time.sleep(0.05)

    print("Attempting to approve after expiration deadline...")
    try:
        executor_exp.approve_step(req_exp_id, decided_by="late_manager")
    except ApprovalExpiredError as e:
        print(f"  [PASSED] Approval rejected due to expiry: {e}")

    print(f"Workflow State: {executor_exp.current_state.value}")
    print(f"Tool executed? {s_expire.result is not None} (Guaranteed False)")

    # -------------------------------------------------------------------------
    # SCENARIO 5: TIMEOUTS & BOUNDED RETRIES FOR IDEMPOTENT CALLS
    # -------------------------------------------------------------------------
    banner("Scenario 5: Timeouts & Bounded Retries for Idempotent Calls")
    attempts = {"count": 0}

    def retryable_mock(args):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ToolExecutionError("Mock network socket blip", tool_name="format_notes")
        return {"status": "success", "formatted_notes": "- Recovered after retry"}

    test_reg = ToolRegistry()
    test_reg._executors["format_notes"] = retryable_mock

    s_retry = WorkflowStep(
        step_id="step-retry",
        name="Idempotent Call with Retries",
        tool_name="format_notes",
        arguments={"text": "Temporary failure test"},
        is_consequential=False,
        is_idempotent=True,
        max_retries=2,
    )
    plan_retry = WorkflowPlan(
        session_id="sess-retry-404",
        correlation_id="corr-retry-404",
        title="Bounded Retry Plan",
        steps=[s_retry],
    )

    executor_ret = WorkflowExecutor(tool_registry=test_reg)
    res_ret = executor_ret.start_workflow(plan_retry)
    print(f"Workflow State: {res_ret['result'].final_state.value}")
    print(f"Retries Attempted: {s_retry.retry_count} (Bounded by max_retries={s_retry.max_retries})")
    print(f"Total Invocations: {attempts['count']}")

    # -------------------------------------------------------------------------
    # SCENARIO 6: WORKFLOW CANCELLATION
    # -------------------------------------------------------------------------
    banner("Scenario 6: Workflow Cancellation")
    s_cancel = WorkflowStep(
        step_id="step-cancel",
        name="Pending Action",
        tool_name="schedule_reminder",
        arguments={"title": "Will be cancelled", "delay_minutes": 10},
        is_consequential=True,
    )
    plan_cancel = WorkflowPlan(
        session_id="sess-cancel-505",
        correlation_id="corr-cancel-505",
        title="Cancel Plan",
        steps=[s_cancel],
    )

    executor_can = WorkflowExecutor()
    executor_can.start_workflow(plan_cancel)
    print(f"Workflow State before cancel: {executor_can.current_state.value}")
    res_can = executor_can.cancel_workflow(reason="User clicked Cancel button in UI")
    print(f"Workflow State after cancel: {res_can.final_state.value}")
    print(f"Step Status: {s_cancel.status.value}")
    print(f"Pending Approvals Remaining: {len(executor_can.pending_approvals)}")

    # -------------------------------------------------------------------------
    # SCENARIO 7: AUDIT EVENT TIMELINE INSPECTION
    # -------------------------------------------------------------------------
    banner("Scenario 7: Audit Event Trail Inspection (EventEnvelope)")
    print(f"Audit events emitted for Approved Plan ({len(final_out['result'].audit_events)} total):")
    for idx, evt in enumerate(final_out['result'].audit_events, 1):
        print(f"  [{idx}] {evt.event_type:<28} | producer={evt.producer:<24} | ts={evt.timestamp.isoformat()}")

    banner("All Week 2 Agentic Workflow Demonstrations Completed Successfully")


if __name__ == "__main__":
    run_demo()
