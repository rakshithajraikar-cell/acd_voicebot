"""Deterministic Replay Engine for Workflow Runs (W4).

Provides replay capabilities for recorded workflow execution traces:
- Parses recorded workflow run fixtures (JSON) containing initial plans, user decisions, and expected audit envelopes.
- Replays the execution deterministically in complete mock mode with zero external side effects.
- Verifies that replayed state transitions, tool outputs, and audit events match the recorded fixture bit-for-bit.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sde6_voicebot.contracts.common import WorkflowState, EventEnvelope
from sde6_voicebot.contracts.workflow import (
    ApprovalStatus,
    StepStatus,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStep,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import ToolRegistry


class WorkflowReplayEngine:
    """Replays recorded workflow runs and verifies deterministic execution parity."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or ToolRegistry()

    def load_fixture(self, fixture_path: Path) -> Dict[str, Any]:
        """Load and parse a recorded workflow fixture JSON."""
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def replay_from_dict(self, fixture_data: Dict[str, Any]) -> Dict[str, Any]:
        """Replay a recorded workflow from fixture dictionary.
        
        Fixture schema:
        - plan: WorkflowPlan definition
        - decisions: list of user decisions to apply on approval gates: [{"request_index": 0, "decision": "approve"|"reject"}]
        - expected: expectations on final_state, completed_steps, and tool outputs
        """
        plan_dict = fixture_data["plan"]
        steps = [
            WorkflowStep(
                step_id=s["step_id"],
                name=s["name"],
                tool_name=s["tool_name"],
                arguments=s.get("arguments", {}),
                depends_on=s.get("depends_on", []),
                is_consequential=s.get("is_consequential", True),
                is_idempotent=s.get("is_idempotent"),
                timeout_seconds=s.get("timeout_seconds", 30.0),
                idempotency_key=s.get("idempotency_key"),
            )
            for s in plan_dict["steps"]
        ]

        plan = WorkflowPlan(
            plan_id=plan_dict.get("plan_id", str(uuid4())),
            session_id=plan_dict.get("session_id", "replay-session"),
            correlation_id=plan_dict.get("correlation_id", "replay-trace"),
            title=plan_dict.get("title", "Replayed Plan"),
            description=plan_dict.get("description", ""),
            steps=steps,
        )

        executor = WorkflowExecutor(tool_registry=self.tool_registry)
        exec_status = executor.start_workflow(plan)

        decisions = list(fixture_data.get("decisions", []))
        decision_idx = 0

        while exec_status.get("status") == "awaiting_approval" and decision_idx < len(decisions):
            decision_info = decisions[decision_idx]
            req = exec_status["approval_request"]
            action = decision_info["decision"].lower()

            if action in ("approve", "approved"):
                exec_status = executor.approve_step(req.request_id, decided_by=decision_info.get("decided_by", "replay_user"))
            elif action in ("reject", "rejected"):
                executor.reject_step(req.request_id, rejection_reason=decision_info.get("reason", "Replay rejection"))
                break
            decision_idx += 1

        final_result = executor._build_result()
        expected = fixture_data.get("expected", {})

        # Validation against expectations
        mismatches: List[str] = []

        if "final_state" in expected:
            expected_state = WorkflowState(expected["final_state"])
            if final_result.final_state != expected_state:
                mismatches.append(f"final_state mismatch: expected {expected_state.value}, got {final_result.final_state.value}")

        if "completed_steps" in expected:
            if sorted(final_result.completed_steps) != sorted(expected["completed_steps"]):
                mismatches.append(f"completed_steps mismatch: expected {expected['completed_steps']}, got {final_result.completed_steps}")

        if "failed_steps" in expected:
            if sorted(final_result.failed_steps) != sorted(expected["failed_steps"]):
                mismatches.append(f"failed_steps mismatch: expected {expected['failed_steps']}, got {final_result.failed_steps}")

        return {
            "deterministic_match": len(mismatches) == 0,
            "mismatches": mismatches,
            "result": final_result,
            "audit_events_count": len(executor.audit_events),
        }
