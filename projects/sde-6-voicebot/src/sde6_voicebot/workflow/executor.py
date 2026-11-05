"""Workflow Executor implementation with safety policies, approval expiry, bounded retries, and timeouts.

Enforces:
- Plan validation: structural integrity, cycle detection, tool allow-list, argument validation, and permission scopes
- Mandatory human approval gate for consequential actions (defaulting to awaiting approval)
- Strict rejection guarantee: rejected action NEVER executes tool and emits a safe audit event
- Strict expiry guarantee: expired approval NEVER executes tool and emits a safe audit event
- Step-level execution timeouts
- Bounded retries strictly restricted to idempotent calls (non-idempotent calls never retry)
- Workflow cancellation support across active and paused states
- Complete immutable audit trail via EventEnvelope records
"""

import concurrent.futures
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Optional, Set
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
    ApprovalExpiredError,
    InvalidPlanError,
    PermissionScopeError,
    ToolArgumentError,
    ToolExecutionError,
    ToolSecurityError,
    WorkflowCancelledError,
    WorkflowTimeoutError,
)
from sde6_voicebot.workflow.state_machine import WorkflowStateMachine
from sde6_voicebot.workflow.tools import ToolRegistry
from sde6_voicebot.workflow.validator import PlanValidator


class WorkflowExecutor:
    """Safe executor for validated workflow plans with approval gating, timeouts, retries, and cancellation."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        granted_scopes: Optional[Set[str]] = None,
        default_step_timeout_seconds: float = 30.0,
        default_approval_ttl_seconds: float = 300.0,
    ):
        self.tool_registry = tool_registry or ToolRegistry(granted_scopes=granted_scopes)
        self.granted_scopes: Optional[Set[str]] = granted_scopes
        self.default_step_timeout_seconds = default_step_timeout_seconds
        self.default_approval_ttl_seconds = default_approval_ttl_seconds
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

    def _emit_event(
        self,
        event_type: str,
        session_id: str,
        correlation_id: str,
        payload: Dict[str, Any],
    ) -> EventEnvelope:
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

    def validate_plan_safety(self, plan: WorkflowPlan, enforce_arguments: bool = False) -> List[str]:
        """Validate plan structure, DAG cycles, tool allow-list, and permission scopes.
        
        Args:
            plan: The WorkflowPlan to validate
            enforce_arguments: If True, also pre-validates step arguments. Defaults to False so execution-time errors are handled by the state machine.
        """
        return PlanValidator.validate(
            plan=plan,
            tool_registry=self.tool_registry,
            granted_scopes=self.granted_scopes,
            enforce_arguments=enforce_arguments,
        )

    def start_workflow(self, plan: WorkflowPlan) -> Dict[str, Any]:
        """Validate, initialize, and begin executing a workflow plan.
        
        Args:
            plan: The WorkflowPlan to execute
            
        Returns:
            Dict containing execution status, current state, and pending approval or final result
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

    def check_and_expire_pending(self, now: Optional[datetime] = None) -> List[str]:
        """Check all pending approval requests and automatically expire those past their deadline."""
        expired_ids = []
        for req_id, req in list(self._pending_approvals.items()):
            if req.is_expired(now=now):
                self.expire_step(req_id, reason="Approval TTL expired")
                expired_ids.append(req_id)
        return expired_ids

    def approve_step(self, request_id: str, decided_by: str = "user") -> Dict[str, Any]:
        """Approve a pending consequential action and resume execution.
        
        Safety guarantee:
        If the approval has expired, approval is rejected and tool is NEVER executed.
        """
        if not self._active_plan or not self._state_machine:
            raise InvalidPlanError("No active workflow plan to approve")

        if request_id not in self._pending_approvals:
            raise InvalidPlanError(f"Approval request '{request_id}' not found or already decided")

        approval = self._pending_approvals[request_id]

        # Check expiration
        if approval.is_expired():
            self.expire_step(request_id, reason="Approval expired before decision")
            raise ApprovalExpiredError(
                f"Approval request '{request_id}' expired at {approval.expires_at} and cannot be approved",
                request_id=request_id,
                correlation_id=self._active_plan.correlation_id,
            )

        # Remove from pending
        self._pending_approvals.pop(request_id)

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
            expires_at=approval.expires_at,
            ttl_seconds=approval.ttl_seconds,
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
                return self._execute_single_step(step)

        return self._run_executable_steps()

    def reject_step(
        self,
        request_id: str,
        rejection_reason: str = "User declined action",
        decided_by: str = "user",
    ) -> WorkflowResult:
        """Reject a pending consequential action.
        
        Safety guarantee:
        Rejection strictly guarantees the tool will NEVER be executed.
        Transitions workflow to CANCELLED and logs a safe audit event.
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
            expires_at=approval.expires_at,
            ttl_seconds=approval.ttl_seconds,
        )

        # Record safe audit event
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
        if self._state_machine.can_transition_to(WorkflowState.CANCELLED):
            self._state_machine.transition_to(WorkflowState.CANCELLED, reason=f"Step {updated_approval.step_id} rejected by user")
            self._active_plan.state = WorkflowState.CANCELLED

        return self._build_result()

    def expire_step(self, request_id: str, reason: str = "Approval request expired") -> WorkflowResult:
        """Expire a pending consequential action that has exceeded its TTL deadline.
        
        Safety guarantee:
        Expiry strictly guarantees the tool will NEVER be executed.
        Transitions workflow to CANCELLED and logs a safe audit event.
        """
        if not self._active_plan or not self._state_machine:
            raise InvalidPlanError("No active workflow plan to expire")

        if request_id not in self._pending_approvals:
            raise InvalidPlanError(f"Approval request '{request_id}' not found")

        approval = self._pending_approvals.pop(request_id)
        updated_approval = ApprovalRequest(
            request_id=approval.request_id,
            workflow_id=approval.workflow_id,
            step_id=approval.step_id,
            tool_name=approval.tool_name,
            action_summary=approval.action_summary,
            parameters=approval.parameters,
            consequential_reason=approval.consequential_reason,
            status=ApprovalStatus.EXPIRED,
            requested_at=approval.requested_at,
            decided_at=datetime.now(timezone.utc),
            decided_by="system.expiry_monitor",
            rejection_reason=reason,
            expires_at=approval.expires_at,
            ttl_seconds=approval.ttl_seconds,
        )

        # Record safe audit event
        self._emit_event(
            event_type="workflow.approval_expired",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={
                "request_id": request_id,
                "step_id": updated_approval.step_id,
                "tool_name": updated_approval.tool_name,
                "expiry_reason": reason,
                "tool_executed": False,
            },
        )

        # Mark gated step as CANCELLED (never executed)
        for step in self._active_plan.steps:
            if step.step_id == updated_approval.step_id:
                step.status = StepStatus.CANCELLED
                step.error = f"Approval expired: {reason}"
            elif step.status in {StepStatus.PENDING, StepStatus.AWAITING_APPROVAL}:
                step.status = StepStatus.CANCELLED
                step.error = "Cancelled due to expired approval"

        # Transition state machine to CANCELLED
        if self._state_machine.can_transition_to(WorkflowState.CANCELLED):
            self._state_machine.transition_to(WorkflowState.CANCELLED, reason=f"Approval expired: {reason}")
            self._active_plan.state = WorkflowState.CANCELLED

        return self._build_result()

    def cancel_workflow(self, reason: str = "User requested cancellation") -> WorkflowResult:
        """Cancel an active or paused workflow.
        
        Guarantees:
        - Active plan transitions to CANCELLED state.
        - Any pending steps are marked CANCELLED and never execute.
        - Emits safe 'workflow.cancelled' audit event.
        """
        if not self._active_plan or not self._state_machine:
            raise InvalidPlanError("No active workflow plan to cancel")

        if self._state_machine.is_terminal:
            raise WorkflowCancelledError(
                f"Cannot cancel workflow in terminal state '{self._state_machine.current_state.value}'",
                correlation_id=self._active_plan.correlation_id,
            )

        # Transition to CANCELLED
        self._state_machine.transition_to(WorkflowState.CANCELLED, reason=reason)
        self._active_plan.state = WorkflowState.CANCELLED

        # Cancel all unexecuted steps
        for step in self._active_plan.steps:
            if step.status in {StepStatus.PENDING, StepStatus.AWAITING_APPROVAL, StepStatus.RUNNING}:
                step.status = StepStatus.CANCELLED
                step.error = f"Workflow cancelled: {reason}"

        # Clear any pending approvals
        self._pending_approvals.clear()

        self._emit_event(
            event_type="workflow.cancelled",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={"plan_id": self._active_plan.plan_id, "reason": reason},
        )

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

        # Check overall completion
        if all(s.status == StepStatus.SUCCEEDED for s in self._active_plan.steps):
            if self._state_machine.current_state != WorkflowState.SUCCEEDED:
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
        """Halt execution and create an ApprovalRequest with expiry for a consequential step."""
        assert self._active_plan is not None
        assert self._state_machine is not None

        if self._state_machine.current_state in {WorkflowState.DRAFT, WorkflowState.RUNNING}:
            self._state_machine.transition_to(WorkflowState.AWAITING_APPROVAL, reason=f"Step {step.step_id} requires approval")

        self._active_plan.state = WorkflowState.AWAITING_APPROVAL
        step.status = StepStatus.AWAITING_APPROVAL

        now = datetime.now(timezone.utc)
        ttl = self.default_approval_ttl_seconds
        expires_at = now + timedelta(seconds=ttl)

        approval_request = ApprovalRequest(
            request_id=str(uuid4()),
            workflow_id=self._active_plan.plan_id,
            step_id=step.step_id,
            tool_name=step.tool_name,
            action_summary=f"Execute {step.name} using {step.tool_name}",
            parameters=step.arguments,
            consequential_reason=f"Action '{step.tool_name}' has persistent consequences and requires explicit confirmation",
            status=ApprovalStatus.PENDING,
            requested_at=now,
            expires_at=expires_at,
            ttl_seconds=ttl,
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
                "expires_at": expires_at.isoformat(),
                "ttl_seconds": ttl,
            },
        )

        return {
            "status": "awaiting_approval",
            "approval_request": approval_request,
            "step_id": step.step_id,
            "plan_id": self._active_plan.plan_id,
        }

    def _execute_with_timeout(self, step: WorkflowStep, timeout_seconds: float) -> Dict[str, Any]:
        """Execute tool call enforced by timeout."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self.tool_registry.execute_tool,
                step.tool_name,
                step.arguments,
                self.granted_scopes,
                self._active_plan.correlation_id,
            )
            try:
                return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError as exc:
                raise WorkflowTimeoutError(
                    f"Step '{step.step_id}' using '{step.tool_name}' timed out after {timeout_seconds} seconds",
                    step_id=step.step_id,
                    timeout_seconds=timeout_seconds,
                    correlation_id=self._active_plan.correlation_id,
                ) from exc

    def _execute_single_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single step with timeout, error handling, and bounded idempotent retries."""
        assert self._active_plan is not None
        assert self._state_machine is not None

        if self._state_machine.current_state == WorkflowState.DRAFT:
            self._state_machine.transition_to(WorkflowState.RUNNING, reason=f"Starting step {step.step_id}")
            self._active_plan.state = WorkflowState.RUNNING

        step.status = StepStatus.RUNNING
        timeout = step.timeout_seconds if step.timeout_seconds is not None else self.default_step_timeout_seconds

        # Determine idempotency: step override takes precedence over tool definition
        tool_spec = self.tool_registry.get_spec(step.tool_name)
        is_idempotent = step.is_idempotent if step.is_idempotent is not None else tool_spec.is_idempotent
        max_retries = step.max_retries if is_idempotent else 0

        self._emit_event(
            event_type="workflow.step_started",
            session_id=self._active_plan.session_id,
            correlation_id=self._active_plan.correlation_id,
            payload={
                "step_id": step.step_id,
                "tool_name": step.tool_name,
                "is_idempotent": is_idempotent,
                "timeout_seconds": timeout,
                "max_retries": max_retries,
            },
        )

        while True:
            try:
                output = self._execute_with_timeout(step, timeout_seconds=timeout)
                step.status = StepStatus.SUCCEEDED
                step.result = output

                self._emit_event(
                    event_type="workflow.step_completed",
                    session_id=self._active_plan.session_id,
                    correlation_id=self._active_plan.correlation_id,
                    payload={"step_id": step.step_id, "tool_name": step.tool_name, "status": "succeeded"},
                )
                return self._run_executable_steps()

            except WorkflowTimeoutError as exc:
                self._emit_event(
                    event_type="workflow.step_timeout",
                    session_id=self._active_plan.session_id,
                    correlation_id=self._active_plan.correlation_id,
                    payload={"step_id": step.step_id, "tool_name": step.tool_name, "timeout_seconds": timeout},
                )
                # Check bounded retry for idempotent call
                if is_idempotent and step.retry_count < max_retries:
                    step.retry_count += 1
                    self._emit_event(
                        event_type="workflow.step_retry",
                        session_id=self._active_plan.session_id,
                        correlation_id=self._active_plan.correlation_id,
                        payload={
                            "step_id": step.step_id,
                            "tool_name": step.tool_name,
                            "attempt": step.retry_count,
                            "max_retries": max_retries,
                            "error": str(exc),
                        },
                    )
                    continue

                return self._handle_step_failure(step, exc)

            except Exception as exc:
                # Check bounded retry for idempotent call
                if is_idempotent and step.retry_count < max_retries:
                    step.retry_count += 1
                    self._emit_event(
                        event_type="workflow.step_retry",
                        session_id=self._active_plan.session_id,
                        correlation_id=self._active_plan.correlation_id,
                        payload={
                            "step_id": step.step_id,
                            "tool_name": step.tool_name,
                            "attempt": step.retry_count,
                            "max_retries": max_retries,
                            "error": str(exc),
                        },
                    )
                    continue

                return self._handle_step_failure(step, exc)

    def _handle_step_failure(self, step: WorkflowStep, exc: Exception) -> Dict[str, Any]:
        """Handle final step failure after retries exhausted or non-idempotent rejection."""
        assert self._active_plan is not None
        assert self._state_machine is not None

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
        """Construct the immutable WorkflowResult with complete audit log."""
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
