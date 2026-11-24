"""UI Workflow Controller (W4 <-> W6 Integration).

Provides an API controller interface for Frontend and User Experience (Shivani Adaragunchi).
Supports querying pending approval gates, streaming progress metrics, and dispatching
user decisions (approve/reject) with strict duplicate prevention and expiry enforcement.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sde6_voicebot.contracts.workflow import (
    ApprovalRequest,
    ApprovalStatus,
    StepStatus,
    WorkflowPlan,
    WorkflowResult,
)
from sde6_voicebot.workflow.exceptions import (
    ApprovalExpiredError,
    DuplicateApprovalError,
    InvalidPlanError,
)
from sde6_voicebot.workflow.executor import WorkflowExecutor


class UIWorkflowController:
    """Controller exposing workflow operations and approval actions to Frontend UI."""

    def __init__(self, executor: WorkflowExecutor):
        self.executor = executor
        self._action_history: List[Dict[str, Any]] = []

    def get_ui_summary(self) -> Dict[str, Any]:
        """Generate a complete UI-ready snapshot of active workflow state and progress."""
        plan = self.executor._active_plan
        if not plan:
            return {
                "active": False,
                "state": "idle",
                "progress_percent": 0.0,
                "pending_approvals": [],
                "steps": [],
            }

        total_steps = len(plan.steps)
        completed_steps = len([s for s in plan.steps if s.status == StepStatus.SUCCEEDED])
        failed_steps = len([s for s in plan.steps if s.status in (StepStatus.FAILED, StepStatus.CANCELLED)])
        progress = round((completed_steps / total_steps) * 100.0, 1) if total_steps > 0 else 0.0

        ui_steps = [
            {
                "step_id": s.step_id,
                "name": s.name,
                "tool_name": s.tool_name,
                "status": s.status.value,
                "is_consequential": s.is_consequential,
                "is_idempotent": s.is_idempotent,
                "has_result": s.result is not None,
                "error": s.error,
            }
            for s in plan.steps
        ]

        pending_cards = [
            {
                "request_id": req.request_id,
                "step_id": req.step_id,
                "tool_name": req.tool_name,
                "title": req.action_summary,
                "consequential_reason": req.consequential_reason,
                "parameters": req.parameters,
                "requested_at": req.requested_at.isoformat(),
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
                "ttl_seconds": req.ttl_seconds,
                "is_expired": req.is_expired(),
            }
            for req in self.executor.pending_approvals.values()
        ]

        return {
            "active": True,
            "plan_id": plan.plan_id,
            "title": plan.title,
            "state": self.executor.current_state.value if self.executor.current_state else "unknown",
            "progress_percent": progress,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "pending_approvals": pending_cards,
            "steps": ui_steps,
        }

    def submit_approval_decision(
        self,
        request_id: str,
        decision: str,  # "approve" or "reject"
        user_name: str = "ui_user",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a user decision from the UI.
        
        Guarantees:
        - "approve": Validates TTL; rejects if expired or duplicate; resumes execution.
        - "reject": Strictly prevents tool execution; cancels workflow; records audit event.
        - Duplicate submissions are caught and safely rejected.
        """
        normalized_decision = decision.lower().strip()

        # Check for duplicate submission first
        if request_id in self.executor.decided_approvals:
            raise DuplicateApprovalError(
                f"Approval request '{request_id}' has already been decided",
                request_id=request_id,
            )

        if normalized_decision in ("approve", "approved", "accept"):
            result = self.executor.approve_step(request_id=request_id, decided_by=user_name)
            self._action_history.append({
                "request_id": request_id,
                "action": "approved",
                "user": user_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {"status": "approved", "execution_result": result}

        elif normalized_decision in ("reject", "rejected", "decline"):
            rejection_reason = reason or "Declined via User Interface"
            workflow_res = self.executor.reject_step(
                request_id=request_id,
                rejection_reason=rejection_reason,
                decided_by=user_name,
            )
            self._action_history.append({
                "request_id": request_id,
                "action": "rejected",
                "user": user_name,
                "reason": rejection_reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {"status": "rejected", "workflow_result": workflow_res}

        else:
            raise ValueError(f"Invalid UI approval decision '{decision}'. Expected 'approve' or 'reject'.")
