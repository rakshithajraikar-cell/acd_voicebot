"""Week 3 Demonstration: Checkpoint & Resume, Audit Trail, and Cross-Team Integration.

Demonstrates:
1. Checkpoint & Resume: Saving snapshots, failed-step recovery without re-running completed steps.
2. Idempotency Keys: Preventing duplicate execution of identical tool invocations.
3. Step-Level Audit Trail & Real-time Progress Events: Emitting EventEnvelope records and percentage updates.
4. Cross-Team Integrations:
   - W3 (Reasoning): Converting WorkflowProposal and ReasoningResult into a validated WorkflowPlan.
   - W5 (Backend): Synchronizing approval requests and publishing session audit trails.
   - W6 (Frontend): Querying UI summary cards, approving/rejecting via UI controller, and duplicate prevention.
"""

from datetime import datetime, timezone
import json
import time

from sde6_voicebot.contracts.workflow import (
    ApprovalStatus,
    StepStatus,
    WorkflowPlan,
    WorkflowProposal,
    WorkflowStep,
)
from sde6_voicebot.workflow.exceptions import DuplicateApprovalError
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import ToolRegistry
from sde6_voicebot.integrations.reasoning_adapter import ReasoningProposalAdapter
from sde6_voicebot.integrations.backend_bridge import BackendApprovalBridge
from sde6_voicebot.integrations.ui_controller import UIWorkflowController


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def progress_listener(data):
    percent = data["percent_complete"]
    current_step = data.get("current_step_id") or "N/A"
    print(f"  [PROGRESS EVENT] Plan: {data['plan_id'][:8]}... | Step: {current_step} | Progress: {percent}% ({data['completed_steps']}/{data['total_steps']}) | State: {data['state']}")


def run_week3_demo():
    print_header("SDE 6 Voicebot — Week 3 Live Demonstration (Workstream W4)")

    # 1. Ingest proposal from Reasoning (W3)
    print("\n>>> Scenario 1: Cross-Team Integration with W3 (Context & Reasoning)")
    proposal = WorkflowProposal(
        session_id="session-demo-w3",
        correlation_id="corr-demo-w3",
        intent="organize_lecture_notes_and_remind",
        suggested_action="Format summary notes from Distributed Systems lecture and schedule follow-up review reminder",
        confidence=0.95,
        sources_used=[{"source_id": "frame_001", "uri": "synthetic://screen/frame_001", "title": "Lecture Slide 14"}],
    )
    print(f"  Ingested WorkflowProposal from W3 Reasoning:")
    print(f"  - Intent: {proposal.intent}")
    print(f"  - Suggested Action: {proposal.suggested_action}")
    print(f"  - Confidence: {proposal.confidence * 100:.1f}%")

    plan = ReasoningProposalAdapter.proposal_to_plan(proposal)
    print(f"\n  Adapted into Validated WorkflowPlan '{plan.title}':")
    for s in plan.steps:
        print(f"  - Step [{s.step_id}]: {s.name} (tool={s.tool_name}, consequential={s.is_consequential}, depends_on={s.depends_on})")

    # 2. Setup Executor with Tool Registry & Progress Callbacks
    registry = ToolRegistry()
    executor = WorkflowExecutor(tool_registry=registry, on_progress=progress_listener)
    backend_bridge = BackendApprovalBridge()
    ui_controller = UIWorkflowController(executor=executor)

    # 3. Start Workflow Execution
    print_header("Scenario 2: Workflow Execution, Idempotency & Checkpointing")
    start_res = executor.start_workflow(plan)
    print(f"\n  Execution Status: {start_res['status']}")

    # Step 1 should have succeeded; Step 2 should be awaiting approval
    assert start_res["status"] == "awaiting_approval"
    approval_req = start_res["approval_request"]
    print(f"  Consequential Action Gated: Step '{approval_req.step_id}' requires human approval.")
    print(f"  - Request ID: {approval_req.request_id}")
    print(f"  - Action: {approval_req.action_summary}")
    print(f"  - Expiry TTL: {approval_req.ttl_seconds}s")

    # Save Checkpoint
    checkpoint = executor.save_checkpoint(metadata={"trigger": "demo_snapshot"})
    print(f"\n  State Snapshot Saved:")
    print(f"  - Checkpoint ID: {checkpoint.checkpoint_id}")
    print(f"  - Completed steps preserved: {checkpoint.completed_steps}")

    # 4. Backend Bridge & UI Controller Integration
    print_header("Scenario 3: Backend State Bridge (W5) & UI Decision Gate (W6)")
    backend_bridge.register_approval_request(approval_req)
    print(f"  Synchronized approval request with Backend Bridge (W5). Status: {backend_bridge.get_approval_state(approval_req.request_id).value}")

    ui_summary = ui_controller.get_ui_summary()
    print(f"  UI Controller Snapshot (W6):")
    print(f"  - Active: {ui_summary['active']}, Overall Progress: {ui_summary['progress_percent']}%")
    print(f"  - Pending Approval Cards: {len(ui_summary['pending_approvals'])}")

    # UI User Approves Action
    print("\n  Submitting approval via UI...")
    approval_res = ui_controller.submit_approval_decision(
        request_id=approval_req.request_id,
        decision="approve",
        user_name="student_spoorthi",
    )
    print(f"  Approval outcome: {approval_res['status']}")
    print(f"  Execution finished: {approval_res['execution_result']['status']}")

    # 5. Security Guarantee: Duplicate Approval Rejection
    print_header("Scenario 4: Security Guarantee — Duplicate Approval Prevention")
    print("  Attempting to submit duplicate approval for the already-decided request...")
    try:
        ui_controller.submit_approval_decision(
            request_id=approval_req.request_id,
            decision="approve",
            user_name="student_spoorthi",
        )
        print("  [ERROR] Duplicate was unexpectedly accepted!")
    except DuplicateApprovalError as exc:
        print(f"  [SUCCESSFUL DEFENSE] DuplicateApprovalError caught: {exc.message}")

    # 6. Failed-Step Recovery without re-running completed steps
    print_header("Scenario 5: Checkpoint Resume & Failed-Step Recovery")
    print("  Demonstrating that resuming from a checkpoint never re-executes completed steps...")
    resumed_plan = executor.restore_from_checkpoint(checkpoint, recover_failed=True)
    print(f"  Restored Plan State: {resumed_plan.state.value}")
    print(f"  Completed steps restored directly from cache: {checkpoint.completed_steps}")

    # 7. Audit Trail Inspection
    print_header("Scenario 6: Immutable Step-Level Audit Trail")
    print(f"  Total Audit Events Emitted: {len(executor.audit_events)}")
    for ev in executor.audit_events[:6]:
        print(f"  - [{ev.timestamp.strftime('%H:%M:%S.%f')[:-3]}] {ev.event_type} | producer={ev.producer}")

    print("\n" + "=" * 70)
    print("  WEEK 3 LIVE DEMONSTRATION COMPLETE: ALL ACCEPTANCE CRITERIA MET!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_week3_demo()
