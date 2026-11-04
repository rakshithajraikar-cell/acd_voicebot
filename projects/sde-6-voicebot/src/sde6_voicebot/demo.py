"""Day 7 Runnable Demonstration Script for W4 Agentic Workflow.

Demonstrates:
1. Rejection of invalid plans (dependency cycles & unauthorized tools)
2. Execution of harmless, non-consequential tool without approval ('format_notes')
3. Human-in-the-loop approval gate on consequential action ('schedule_reminder'):
   a. Rejection path: Action declined -> tool NEVER executes, safe cancellation audit event recorded
   b. Approval path: Action approved -> tool executes cleanly through to SUCCEEDED
4. Complete audit event timeline with EventEnvelope records
"""

import json
from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.contracts.workflow import WorkflowPlan, WorkflowStep
from sde6_voicebot.workflow.exceptions import ToolSecurityError
from sde6_voicebot.workflow.executor import WorkflowExecutor


def banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title.upper()}")
    print("=" * 70)


def run_demo():
    banner("Academiaai AI Voicebot - SDE 6 (W4 Agentic Workflow Demo)")
    print("Owner: Spoorthi Y D (W4 Agentic Workflow)")
    print("Mode: Safe Mock Mode (No external network, no unapproved execution)")

    # ---------------------------------------------------------
    # SCENARIO 1: Invalid Plan Rejection (Cycle Detection & Security)
    # ---------------------------------------------------------
    banner("Scenario 1: Invalid Plan & Security Rejections")
    print("1a. Testing Cyclic Dependency Detection (Step A <-> Step B)...")
    try:
        step_a = WorkflowStep(step_id="step-a", name="A", tool_name="format_notes", depends_on=["step-b"], is_consequential=False)
        step_b = WorkflowStep(step_id="step-b", name="B", tool_name="format_notes", depends_on=["step-a"], is_consequential=False)
        WorkflowPlan(session_id="s1", correlation_id="c1", title="Cycle Plan", steps=[step_a, step_b])
    except Exception as e:
        print(f"  [PASSED] Schema rejected cycle: {e}")

    print("\n1b. Testing Disallowed Tool Blocking ('exec_shell')...")
    try:
        bad_step = WorkflowStep(step_id="s-bad", name="Shell", tool_name="exec_shell", is_consequential=True)
        bad_plan = WorkflowPlan(session_id="s1", correlation_id="c1", title="Bad Tool Plan", steps=[bad_step])
        executor = WorkflowExecutor()
        executor.start_workflow(bad_plan)
    except ToolSecurityError as e:
        print(f"  [PASSED] Security policy blocked unauthorized tool: {e}")

    # ---------------------------------------------------------
    # SCENARIO 2: Purely Harmless Step (Direct Execution)
    # ---------------------------------------------------------
    banner("Scenario 2: Harmless Non-Consequential Execution ('format_notes')")
    notes_text = "Important lecture topics:\n• Agentic State Machines\n• Human-in-the-loop Gates\n• Structured Envelopes"
    step_safe = WorkflowStep(
        step_id="step-notes",
        name="Format Study Notes",
        tool_name="format_notes",
        arguments={"text": notes_text, "bullet_style": "dash"},
        is_consequential=False,
    )
    plan_safe = WorkflowPlan(
        session_id="sess-safe-101",
        correlation_id="corr-safe-101",
        title="Format Notes Workflow",
        steps=[step_safe],
    )

    executor_safe = WorkflowExecutor()
    print(f"Submitting plan '{plan_safe.title}'...")
    res_safe = executor_safe.start_workflow(plan_safe)
    print(f"Execution Status: {res_safe['status']}")
    print(f"Final State: {res_safe['result'].final_state.value}")
    print("Output Data:")
    print(json.dumps(res_safe['result'].step_results["step-notes"], indent=2))

    # ---------------------------------------------------------
    # SCENARIO 3: Consequential Action Approval Gate - Rejection Path
    # ---------------------------------------------------------
    banner("Scenario 3: Consequential Action Rejection Guarantee")
    step_consequential_reject = WorkflowStep(
        step_id="step-remind-reject",
        name="Schedule Alert (Declined by User)",
        tool_name="schedule_reminder",
        arguments={"title": "Unauthorized Notification", "delay_minutes": 30, "priority": "high"},
        is_consequential=True,
    )
    plan_reject = WorkflowPlan(
        session_id="sess-rej-202",
        correlation_id="corr-rej-202",
        title="Rejected Reminder Workflow",
        steps=[step_consequential_reject],
    )

    executor_rej = WorkflowExecutor()
    print(f"Starting workflow with consequential tool '{step_consequential_reject.tool_name}'...")
    pause_outcome = executor_rej.start_workflow(plan_reject)

    print(f"Workflow State: {executor_rej.current_state.value}")
    req = pause_outcome["approval_request"]
    print(f"Approval Request Created: ID={req.request_id}")
    print(f"Consequential Reason: {req.consequential_reason}")

    print("\nSimulating user rejection decision ('User denied permission')...")
    res_rejected = executor_rej.reject_step(req.request_id, rejection_reason="User denied calendar modification", decided_by="spoorthi_user")

    print(f"Final Workflow State: {res_rejected.final_state.value}")
    print(f"Step Result (guaranteed None, never executed): {step_consequential_reject.result}")
    print(f"Step Error Log: {step_consequential_reject.error}")

    # ---------------------------------------------------------
    # SCENARIO 4: Multi-Step Pipeline with Approval Gate - Approval Path
    # ---------------------------------------------------------
    banner("Scenario 4: Multi-Step Pipeline (Safe Step -> Approval Gate -> Tool Execution)")
    s1 = WorkflowStep(
        step_id="step-1-notes",
        name="Organize Voice Transcript",
        tool_name="format_notes",
        arguments={"text": "Review architecture doc\nSubmit PR on time", "bullet_style": "dash"},
        is_consequential=False,
    )
    s2 = WorkflowStep(
        step_id="step-2-reminder",
        name="Set Sprint Review Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "Sprint Review Reminder", "delay_minutes": 45, "priority": "normal"},
        depends_on=["step-1-notes"],
        is_consequential=True,
    )
    pipeline_plan = WorkflowPlan(
        session_id="sess-pipe-303",
        correlation_id="corr-pipe-303",
        title="Voice Notes & Reminder Pipeline",
        steps=[s1, s2],
    )

    executor_pipe = WorkflowExecutor()
    print("Initiating multi-step pipeline...")
    gate_out = executor_pipe.start_workflow(pipeline_plan)

    print(f"Step 1 ('{s1.step_id}') finished: status={s1.status.value}")
    print(f"Step 2 ('{s2.step_id}') halted at approval gate: status={s2.status.value}")
    print(f"Engine State: {executor_pipe.current_state.value}")

    req2_id = gate_out["approval_request"].request_id
    print(f"\nUser explicitly approves Request ID: {req2_id}...")
    final_out = executor_pipe.approve_step(req2_id, decided_by="spoorthi_lead")

    print(f"Pipeline Final State: {final_out['result'].final_state.value}")
    print(f"Completed Steps: {final_out['result'].completed_steps}")
    print("\nResults for Step 1:")
    print(json.dumps(final_out['result'].step_results["step-1-notes"], indent=2))
    print("\nResults for Step 2:")
    print(json.dumps(final_out['result'].step_results["step-2-reminder"], indent=2))

    # ---------------------------------------------------------
    # SCENARIO 5: Audit Event Trail Verification
    # ---------------------------------------------------------
    banner("Scenario 5: Audit Event Trail (EventEnvelope)")
    print(f"Total audit events recorded for pipeline: {len(final_out['result'].audit_events)}")
    for i, event in enumerate(final_out['result'].audit_events, 1):
        print(f"  [{i}] type={event.event_type:<28} producer={event.producer:<24} time={event.timestamp.isoformat()}")

    banner("Day 7 Demonstration Completed Successfully")


if __name__ == "__main__":
    run_demo()
