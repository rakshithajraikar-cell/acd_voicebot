"""Workflow Executor implementation.

Enforces:
- Dependency graph traversal and step ordering
- Strict allow-list tool execution
- Mandatory human approval gate for all consequential actions
- Consequential actions default to awaiting approval and never run unapproved
- Rejection guarantees no tool execution and emits a safe audit event
- Complete audit trail of EventEnvelope records
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sde6_voicebot.contracts.common import EventEnvelope, ErrorEnvelope, WorkflowState
from sde6_voicebot.contracts.workflow import (
    ApprovalRequest,
    ApprovalStatus,
    StepStatus,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStep,
)
from sde6_voicebot.workflow.exceptions import (
    InvalidPlanError,
    ToolExecutionError,
    ToolSecurityError,
)
from sde6_voicebot.workflow.state_machine import WorkflowStateMachine
from sde6_voicebot.workflow.tools import ToolRegistry


class WorkflowExecutor:
    """Safe executor for validated workflow plans with human-in-the-loop approval gating."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or ToolRegistry()
        self.audit_events: List[EventEnvelope] = []
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._active_plan: Optional[WorkflowPlan] = None
        self._state_machine: Optional[WorkflowStateMachine] = None
        self._start_time: float = 0.0

    @property
    def state_machine(self) -> Optional[WorkflowStateMachine]:
        return self._state_machine

    @property
    def current_state(self) -> Optional[WorkflowState]:
        return self._state_machine.current_state if self._state_machine else None

    @property
    def pending_approvals(self) -> Dict[str, ApprovalRequest]:
        return dict(self._pending_approvals)

    def _emit_event(self, event_type: str, session_id: str, correlation_id: str, payload: Dict[str, Any]) -> EventEnvelope:
        """Create and store a standard EventEnvelope audit record."""
        event = EventEnvelope(
            event_id=str(uuid4()),
            event_type=event_type,
            schema_version="1.0.0",
            session_id=session_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            producer="sde6.workflow_executor",
            payload=payload,
        )
        self.audit_events.append(event)
        return event

    def validate_plan_safety(self, plan: WorkflowPlan) -> None:
        """Validate that all tools referenced in the plan are in the strict allow-list."""
        for step in plan.steps:
            if not self.tool_registry.has_tool(step.tool_name):
                raise ToolSecurityError(
                    f"Plan contains non-allowlisted tool '{step.tool_name}' in step '{step.step_id}'. "
                    f"Only allowed mock tools are permitted.",
                    tool_name=step.tool_name,
                    correlation_id=plan.correlation_id,
                )

    def start_workflow(self, plan: WorkflowPlan) -> Dict[str, Any]:
        """Validate, initialize, and start executing a workflow plan.
        
        If a consequential step is encountered requiring approval, execution halts,
        the workflow transitions to AWAITING_APPROVAL, and an ApprovalRequest is returned.
        
        Args:
            plan: The WorkflowPlan to execute
            
        Returns:
            Dict containing current status, state, and pending approval (if any) or final result
        """
        self.validate_plan_safety(plan)
        self._active_plan = plan
        self._start_time = time.time()
        self._pending_approvals.clear()

        # Initialize state machine
        self._state_machine = WorkflowStateMachine(
            initial_state=WorkflowState.DRAFT,
            correlation_id=plan.correlation_id,
        )

        self._emit_event(
            event_type="workflow.initialized",
            session_id=plan.session_id,
            correlation_id=plan.correlation_id,
            payload={"plan_id": plan.plan_id, "title": plan.title, "step_count": len(plan.steps)},
        )

        return self._run_executable_steps()

    def approve_step(self, request_id: str, decided_by: str = "user") -> Dict[str, Any]:
        """Approve a pending consequential action and resume execution.
        
        Args:
            request_id: ID of the pending ApprovalRequest
            decided_by: Username/identifier of approving authority
        """
        if not self._active_plan or not self._state_machine:
            raise InvalidPlanError("No active workflow plan to approve")

        if request_id not in self._pending_approvals:
            raise InvalidPlanError(f"Approval request '{request_id}' not found or already decided")

        approval = self._pending_approvals.pop(request_id)
        # Update approval record
        updated_approval = ApprovalRequest(
            request_id=approval.request_id,
            workflow_id=approval.workflow_id,
            step_id=approval.step_id,
            tool_name=approval.tool_name,
            action_summary=approval.action_summary,
            parameters=approval.parameters,
            consequential_reason=approval.consequential_reason,
            status=ApprovalStatus.APPROVED,
            requested_at=approval.requested_at,
            decided_at=datetime.now(timezone.utc),
            decided_by=decided_by,
        )

        self._emit_event(
            event_type="workflow.approval_granted",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={
                "request_id": request_id,
                "step_id": updated_approval.step_id,
                "tool_name": updated_approval.tool_name,
                "decided_by": decided_by,
            },
        )

        # Transition state machine back to RUNNING
        if self._state_machine.current_state == WorkflowState.AWAITING_APPROVAL:
            self._state_machine.transition_to(WorkflowState.RUNNING, reason=f"Approved step {updated_approval.step_id}")
            self._active_plan.state = WorkflowState.RUNNING

        # Locate the step and mark approved
        for step in self._active_plan.steps:
            if step.step_id == updated_approval.step_id:
                step.status = StepStatus.PENDING
                step.approval_id = request_id
                # Execute the approved step immediately
                return self._execute_single_step(step)

        return self._run_executable_steps()

    def reject_step(self, request_id: str, rejection_reason: str = "User declined action", decided_by: str = "user") -> WorkflowResult:
        """Reject a pending consequential action.
        
        Safety guarantee:
        Rejection strictly guarantees the tool will NEVER be executed.
        Transitions workflow to CANCELLED and logs an audit event.
        """
        if not self._active_plan or not self._state_machine:
            raise InvalidPlanError("No active workflow plan to reject")

        if request_id not in self._pending_approvals:
            raise InvalidPlanError(f"Approval request '{request_id}' not found or already decided")

        approval = self._pending_approvals.pop(request_id)
        updated_approval = ApprovalRequest(
            request_id=approval.request_id,
            workflow_id=approval.workflow_id,
            step_id=approval.step_id,
            tool_name=approval.tool_name,
            action_summary=approval.action_summary,
            parameters=approval.parameters,
            consequential_reason=approval.consequential_reason,
            status=ApprovalStatus.REJECTED,
            requested_at=approval.requested_at,
            decided_at=datetime.now(timezone.utc),
            decided_by=decided_by,
            rejection_reason=rejection_reason,
        )

        # Record audit event
        self._emit_event(
            event_type="workflow.approval_rejected",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={
                "request_id": request_id,
                "step_id": updated_approval.step_id,
                "tool_name": updated_approval.tool_name,
                "rejection_reason": rejection_reason,
                "decided_by": decided_by,
                "tool_executed": False,
            },
        )

        # Mark step as CANCELLED (never executed)
        for step in self._active_plan.steps:
            if step.step_id == updated_approval.step_id:
                step.status = StepStatus.CANCELLED
                step.error = f"Rejected by user: {rejection_reason}"
            elif step.status == StepStatus.PENDING:
                # Cancel all remaining downstream pending steps
                step.status = StepStatus.CANCELLED
                step.error = "Cancelled due to rejected upstream dependency"

        # Transition state machine to CANCELLED
        self._state_machine.transition_to(WorkflowState.CANCELLED, reason=f"Step {updated_approval.step_id} rejected by user")
        self._active_plan.state = WorkflowState.CANCELLED

        return self._build_result()

    def _run_executable_steps(self) -> Dict[str, Any]:
        """Iterate through steps that have their dependencies satisfied."""
        assert self._active_plan is not None
        assert self._state_machine is not None

        # Build map of completed step IDs
        completed_step_ids = {s.step_id for s in self._active_plan.steps if s.status == StepStatus.SUCCEEDED}

        # Find next runnable step
        for step in self._active_plan.steps:
            if step.status != StepStatus.PENDING:
                continue

            # Check if all dependencies are satisfied
            deps_satisfied = all(dep in completed_step_ids for dep in step.depends_on)
            if not deps_satisfied:
                continue

            # Check if step or tool is consequential
            tool_spec = self.tool_registry.get_spec(step.tool_name)
            is_consequential = step.is_consequential or tool_spec.is_consequential

            # Consequential actions MUST be approved before running
            if is_consequential and not step.approval_id:
                return self._gate_consequential_step(step, tool_spec)

            # Non-consequential or pre-approved: execute
            return self._execute_single_step(step)

        # If no more pending steps, check overall completion
        if all(s.status == StepStatus.SUCCEEDED for s in self._active_plan.steps):
            if self._state_machine.current_state != WorkflowState.SUCCEEDED:
                # Can transition from DRAFT or RUNNING to SUCCEEDED
                if self._state_machine.current_state == WorkflowState.DRAFT:
                    self._state_machine.transition_to(WorkflowState.RUNNING, reason="Starting completed execution")
                self._state_machine.transition_to(WorkflowState.SUCCEEDED, reason="All steps completed successfully")
                self._active_plan.state = WorkflowState.SUCCEEDED

            self._emit_event(
                event_type="workflow.completed",
                session_id=self._active_plan.session_id,
                correlation_id=self._active_plan.correlation_id,
                payload={"plan_id": self._active_plan.plan_id, "status": "succeeded"},
            )
            return {"status": "completed", "result": self._build_result()}

        return {"status": "in_progress", "state": self._state_machine.current_state.value}

    def _gate_consequential_step(self, step: WorkflowStep, tool_spec: Any) -> Dict[str, Any]:
        """Halt execution and create an ApprovalRequest for a consequential step."""
        assert self._active_plan is not None
        assert self._state_machine is not None

        # Transition state machine to AWAITING_APPROVAL
        if self._state_machine.current_state == WorkflowState.DRAFT:
            self._state_machine.transition_to(WorkflowState.AWAITING_APPROVAL, reason=f"Step {step.step_id} requires approval")
        elif self._state_machine.current_state == WorkflowState.RUNNING:
            self._state_machine.transition_to(WorkflowState.AWAITING_APPROVAL, reason=f"Step {step.step_id} requires approval")

        self._active_plan.state = WorkflowState.AWAITING_APPROVAL
        step.status = StepStatus.AWAITING_APPROVAL

        approval_request = ApprovalRequest(
            request_id=str(uuid4()),
            workflow_id=self._active_plan.plan_id,
            step_id=step.step_id,
            tool_name=step.tool_name,
            action_summary=f"Execute {step.name} using {step.tool_name}",
            parameters=step.arguments,
            consequential_reason=f"Action '{step.tool_name}' has persistent consequences and requires explicit confirmation",
            status=ApprovalStatus.PENDING,
        )

        self._pending_approvals[approval_request.request_id] = approval_request

        self._emit_event(
            event_type="workflow.approval_requested",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={
                "request_id": approval_request.request_id,
                "step_id": step.step_id,
                "tool_name": step.tool_name,
                "consequential_reason": approval_request.consequential_reason,
            },
        )

        return {
            "status": "awaiting_approval",
            "approval_request": approval_request,
            "step_id": step.step_id,
            "plan_id": self._active_plan.plan_id,
        }

    def _execute_single_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single step that is cleared for running."""
        assert self._active_plan is not None
        assert self._state_machine is not None

        if self._state_machine.current_state == WorkflowState.DRAFT:
            self._state_machine.transition_to(WorkflowState.RUNNING, reason=f"Starting step {step.step_id}")
            self._active_plan.state = WorkflowState.RUNNING

        step.status = StepStatus.RUNNING

        self._emit_event(
            event_type="workflow.step_started",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={"step_id": step.step_id, "tool_name": step.tool_name},
        )

        try:
            output = self.tool_registry.execute_tool(step.tool_name, step.arguments)
            step.status = StepStatus.SUCCEEDED
            step.result = output

            self._emit_event(
                event_type="workflow.step_completed",
                session_id=self._active_plan.session_id,
                correlation_id=self._active_plan.correlation_id,
                payload={"step_id": step.step_id, "tool_name": step.tool_name, "status": "succeeded"},
            )
            # Proceed to next steps
            return self._run_executable_steps()

        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error = str(exc)

            if self._state_machine.can_transition_to(WorkflowState.FAILED):
                self._state_machine.transition_to(WorkflowState.FAILED, reason=f"Step {step.step_id} failed: {exc}")
                self._active_plan.state = WorkflowState.FAILED

            self._emit_event(
                event_type="workflow.step_failed",
                session_id=self._active_plan.session_id,
                correlation_id=self._active_plan.correlation_id,
                payload={"step_id": step.step_id, "tool_name": step.tool_name, "error": str(exc)},
            )
            return {"status": "failed", "result": self._build_result(error_msg=str(exc))}

    def _build_result(self, error_msg: Optional[str] = None) -> WorkflowResult:
        """Construct the immutable WorkflowResult."""
        assert self._active_plan is not None
        assert self._state_machine is not None

        duration = time.time() - self._start_time if self._start_time > 0 else 0.0
        step_results = {s.step_id: s.result for s in self._active_plan.steps if s.result is not None}
        completed = [s.step_id for s in self._active_plan.steps if s.status == StepStatus.SUCCEEDED]
        failed = [s.step_id for s in self._active_plan.steps if s.status in {StepStatus.FAILED, StepStatus.CANCELLED}]

        error_envelope = None
        if error_msg or self._state_machine.current_state in {WorkflowState.FAILED, WorkflowState.CANCELLED}:
            error_envelope = ErrorEnvelope(
                code="WORKFLOW_TERMINATED" if self._state_machine.current_state == WorkflowState.CANCELLED else "WORKFLOW_FAILED",
                message_safe_for_user=error_msg or f"Workflow ended in state {self._state_machine.current_state.value}",
                retryable=False,
                correlation_id=self._active_plan.correlation_id,
            )

        return WorkflowResult(
            workflow_id=self._active_plan.plan_id,
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            final_state=self._state_machine.current_state,
            step_results=step_results,
            completed_steps=completed,
            failed_steps=failed,
            duration_seconds=round(duration, 3),
            audit_events=list(self.audit_events),
            error=error_envelope,
        )
