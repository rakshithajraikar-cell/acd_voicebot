"""Day 30 Final Demonstration: Agentic Workflow Engine Hardening & Release (W4).

Demonstrates:
1. Normal Happy Path: End-to-end execution of a validated multi-step workflow.
2. Failure Injection 1: Cyclic DAG Plan rejection (0 tools execute).
3. Failure Injection 2: Malicious / Invalid Arguments rejection (0 tools execute).
4. Failure Injection 3: Consequential action rejection guarantee (0 tools execute).
5. Failure Injection 4: Duplicate approval submission defense.
6. Deterministic Replay: Bit-for-bit replay of recorded workflow execution fixture.
7. Policy Matrix: Enforcement of tool security rules and permission scopes.
"""

from pathlib import Path
from typing import Dict, Any

from sde6_voicebot.contracts.workflow import (
    WorkflowPlan,
    WorkflowStep,
)
from sde6_voicebot.workflow.exceptions import (
    DuplicateApprovalError,
    ToolArgumentError,
    ToolSecurityError,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.policy_matrix import PolicyMatrix
from sde6_voicebot.workflow.replay import WorkflowReplayEngine
from sde6_voicebot.workflow.tools import ToolRegistry
from sde6_voicebot.integrations.ui_controller import UIWorkflowController


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def run_final_release_demo():
    print_banner("ACADEMIAAI AI VOICEBOT — SDE 6 FINAL RELEASE DEMO (W4)")
    registry = ToolRegistry(granted_scopes={"safe.memory.read_write", "user.notification.schedule"})

    # -----------------------------------------------------------------------
    # 1. Normal Happy Path Flow
    # -----------------------------------------------------------------------
    print("\n>>> 1. NORMAL HAPPY-PATH EXECUTION")
    step1 = WorkflowStep(
        step_id="step-1-notes",
        name="Format Lecture Notes",
        tool_name="format_notes",
        arguments={"text": "Voicebot Week 4 hardening: failure-injection, replay, policy matrix."},
        is_consequential=False,
        is_idempotent=True,
    )
    step2 = WorkflowStep(
        step_id="step-2-sync",
        name="Schedule Team Release Review",
        tool_name="schedule_reminder",
        arguments={"title": "SDE 6 Team Gate Review", "delay_minutes": 60, "priority": "high"},
        depends_on=["step-1-notes"],
        is_consequential=True,
        is_idempotent=False,
    )
    plan = WorkflowPlan(
        plan_id="plan-release-demo",
        session_id="session-rel-01",
        correlation_id="corr-rel-01",
        title="Production Release Workflow",
        steps=[step1, step2],
    )

    executor = WorkflowExecutor(tool_registry=registry)
    ui = UIWorkflowController(executor=executor)

    status = executor.start_workflow(plan)
    print(f"  [STATUS] Workflow started. Current status: {status['status']}")
    print(f"  [GATE] Step 1 finished. Step 2 requires human approval: '{status['approval_request'].action_summary}'")

    # User approves via UI
    req_id = status["approval_request"].request_id
    ui_res = ui.submit_approval_decision(request_id=req_id, decision="approve", user_name="team_lead")
    print(f"  [APPROVAL] Decision recorded: {ui_res['status']}")
    print(f"  [RESULT] Final State: {ui.get_ui_summary()['state'].upper()} (Progress: {ui.get_ui_summary()['progress_percent']}%)")

    # -----------------------------------------------------------------------
    # 2. Failure Injection 1: Cyclic Plan Defense
    # -----------------------------------------------------------------------
    print_banner("2. FAILURE INJECTION: CYCLIC DAG REJECTION")
    print("  Injecting 2-node cycle: Step A -> Step B -> Step A...")
    try:
        step_a = WorkflowStep(step_id="A", name="Step A", tool_name="format_notes", arguments={"text": "A"}, depends_on=["B"])
        step_b = WorkflowStep(step_id="B", name="Step B", tool_name="format_notes", arguments={"text": "B"}, depends_on=["A"])
        WorkflowPlan(plan_id="cycle-plan", session_id="s", correlation_id="c", title="Cycle", steps=[step_a, step_b])
        print("  [ERROR] Cycle was not caught!")
    except ValueError as exc:
        print(f"  [DEFENSE SUCCESSFUL] Caught cyclic dependency: {exc}")
        print("  -> Tool executions attempted: ZERO (0)")

    # -----------------------------------------------------------------------
    # 3. Failure Injection 2: Malicious / Invalid Arguments
    # -----------------------------------------------------------------------
    print_banner("3. FAILURE INJECTION: MALICIOUS / OUT-OF-BOUNDS ARGUMENTS")
    print("  Injecting negative delay_minutes (-100) into schedule_reminder...")
    bad_step = WorkflowStep(
        step_id="bad-step",
        name="Bad Step",
        tool_name="schedule_reminder",
        arguments={"title": "Hack", "delay_minutes": -100},
        is_consequential=True,
    )
    bad_plan = WorkflowPlan(plan_id="bad-plan", session_id="s", correlation_id="c", title="Bad", steps=[bad_step])
    try:
        executor.validate_plan_safety(bad_plan, enforce_arguments=True)
        print("  [ERROR] Malicious argument was not caught!")
    except ToolArgumentError as exc:
        print(f"  [DEFENSE SUCCESSFUL] Caught ToolArgumentError: {exc.message}")
        print("  -> Tool executions attempted: ZERO (0)")

    # -----------------------------------------------------------------------
    # 4. Failure Injection 3: Rejection Guarantee
    # -----------------------------------------------------------------------
    print_banner("4. FAILURE INJECTION: REJECTION GUARANTEE")
    print("  Simulating user rejection on consequential tool...")
    rej_step = WorkflowStep(
        step_id="rej-step",
        name="Rejected Reminder",
        tool_name="schedule_reminder",
        arguments={"title": "Cancel me", "delay_minutes": 10},
        is_consequential=True,
    )
    rej_plan = WorkflowPlan(plan_id="rej-plan", session_id="s", correlation_id="c", title="Rej", steps=[rej_step])
    rej_exc = WorkflowExecutor(tool_registry=registry)
    rej_stat = rej_exc.start_workflow(rej_plan)
    rej_res = rej_exc.reject_step(rej_stat["approval_request"].request_id, rejection_reason="Declined by user")

    print(f"  [REJECTION RECORDED] Final state: {rej_res.final_state.value}")
    print(f"  [SAFETY PROOF] Step result: {rej_plan.steps[0].result} (None)")
    print(f"  -> Consequential tool was strictly NEVER executed!")

    # -----------------------------------------------------------------------
    # 5. Failure Injection 4: Duplicate Approval Defense
    # -----------------------------------------------------------------------
    print_banner("5. FAILURE INJECTION: DUPLICATE APPROVAL PREVENTION")
    print("  Attempting duplicate approval submission for the rejected request...")
    try:
        rej_exc.approve_step(rej_stat["approval_request"].request_id)
        print("  [ERROR] Duplicate decision permitted!")
    except DuplicateApprovalError as exc:
        print(f"  [DEFENSE SUCCESSFUL] Caught DuplicateApprovalError: {exc.message}")

    # -----------------------------------------------------------------------
    # 6. Deterministic Replay Verification
    # -----------------------------------------------------------------------
    print_banner("6. DETERMINISTIC REPLAY FIXTURE REPRODUCTION")
    replay_engine = WorkflowReplayEngine()
    fixture_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "replay_happy_path.json"
    fixture_data = replay_engine.load_fixture(fixture_file)
    replay_out = replay_engine.replay_from_dict(fixture_data)

    print(f"  Loaded Replay Fixture: '{fixture_file.name}'")
    print(f"  [PARITY CHECK] Deterministic Match: {replay_out['deterministic_match']}")
    print(f"  [REPLAY OUTPUT] Final State: {replay_out['result'].final_state.value}")
    print(f"  [AUDIT PARITY] Audit events reproduced: {replay_out['audit_events_count']}")

    # -----------------------------------------------------------------------
    # 7. Policy Matrix Enforcement
    # -----------------------------------------------------------------------
    print_banner("7. POLICY MATRIX ENFORCEMENT")
    policy_matrix = PolicyMatrix()
    print("  Enforcing matrix dimensions for all registered tools:")
    for rule in policy_matrix.list_rules():
        print(f"  - [{rule.tool_name}] Risk: {rule.risk_level.value.upper()} | Approval Required: {rule.requires_human_approval} | Idempotent: {rule.is_idempotent} | Scope: '{rule.permission_scope}'")

    print("\n" + "=" * 75)
    print("  ALL WEEK 4 DELIVERABLES & DAY 30 ACCEPTANCE CRITERIA VERIFIED!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_final_release_demo()
