"""Workflow contract schemas according to W4 deliverables and engineering standards.

Includes:
- ToolSpec (with idempotency and permission scopes)
- ApprovalRequest (with expiry logic and TTL)
- WorkflowStep (with timeout and bounded retry parameters)
- WorkflowPlan (with DAG validation and cycle detection)
- WorkflowResult
"""

from collections import defaultdict, deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from sde6_voicebot.contracts.common import EventEnvelope, ErrorEnvelope, WorkflowState


class ApprovalStatus(str, Enum):
    """Lifecycle status of a human approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class StepStatus(str, Enum):
    """Execution status of an individual workflow step."""
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ToolSpec(BaseModel):
    """Specification of an allowed tool.
    
    Safety rules:
    - Consequential tools default to requiring explicit user approval.
    - Idempotent tools are safe for bounded retries; non-idempotent tools must never retry.
    """
    model_config = ConfigDict(frozen=True)

    tool_id: str = Field(..., description="Unique tool identifier, e.g. 'tool.format_notes'")
    name: str = Field(..., description="Canonical tool name used in step calls")
    description: str = Field(..., description="Clear explanation of the tool's behavior and constraints")
    parameters_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for input parameters")
    is_consequential: bool = Field(default=True, description="True if action has external, stateful, or persistent consequences")
    is_idempotent: bool = Field(default=False, description="True if repeated executions produce identical side effects and are safe to retry")
    permission_scope: str = Field(default="safe.mock", description="Security and permission scope")
    version: str = Field(default="1.0.0", description="Tool schema version")


class ApprovalRequest(BaseModel):
    """Schema for human approval requests for consequential actions.
    
    Safety rules:
    - A consequential action will never execute unless an ApprovalRequest transitions to APPROVED.
    - A rejected or expired approval strictly guarantees no tool execution.
    """
    model_config = ConfigDict(frozen=True)

    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique approval request ID")
    workflow_id: str = Field(..., description="Associated workflow plan ID")
    step_id: str = Field(..., description="Step requiring approval")
    tool_name: str = Field(..., description="Name of the tool being gated")
    action_summary: str = Field(..., description="Human-readable summary of what will happen if approved")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Redacted/safe snapshot of step parameters")
    consequential_reason: str = Field(..., description="Why this step is classified as consequential")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="Current approval status")
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of request")
    decided_at: Optional[datetime] = Field(default=None, description="Timestamp of user decision")
    decided_by: Optional[str] = Field(default=None, description="Actor or username who made the decision")
    rejection_reason: Optional[str] = Field(default=None, description="User or system rationale if rejected")
    expires_at: Optional[datetime] = Field(default=None, description="Expiry timestamp in UTC")
    ttl_seconds: Optional[float] = Field(default=300.0, description="Time-to-live in seconds before automatic expiration")

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check whether this approval request has passed its expiry deadline."""
        if self.status == ApprovalStatus.EXPIRED:
            return True
        if self.expires_at is not None:
            current_time = now or datetime.now(timezone.utc)
            return current_time >= self.expires_at
        return False


class WorkflowStep(BaseModel):
    """Individual executable step within a workflow plan.
    
    Default safety rule: is_consequential defaults to True unless verified harmless.
    """
    model_config = ConfigDict(validate_assignment=True)

    step_id: str = Field(..., description="Unique step identifier within the plan")
    name: str = Field(..., description="Human-readable step title")
    tool_name: str = Field(..., description="Target tool identifier to run")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps that must succeed before this step runs")
    is_consequential: bool = Field(default=True, description="Consequential flag; defaults to True for safety")
    is_idempotent: Optional[bool] = Field(default=None, description="Step-level override for tool idempotency")
    timeout_seconds: Optional[float] = Field(default=30.0, description="Execution timeout for this step in seconds")
    max_retries: int = Field(default=0, description="Max retry attempts for idempotent execution failures")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Step lifecycle status")
    approval_id: Optional[str] = Field(default=None, description="ID of approval request if gated")
    idempotency_key: Optional[str] = Field(default=None, description="Client or step idempotency key to prevent duplicate execution")
    result: Optional[Any] = Field(default=None, description="Tool execution output if succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    @field_validator("step_id")
    @classmethod
    def validate_step_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("step_id cannot be blank")
        return v.strip()


class WorkflowPlan(BaseModel):
    """A validated, structured plan containing one or more dependency-managed steps.
    
    Enforces validation for:
    - Non-empty step list
    - Unique step IDs
    - Referential integrity of depends_on
    - Acyclic dependency graph (DAG)
    """
    model_config = ConfigDict(validate_assignment=True)

    plan_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique workflow plan ID")
    session_id: str = Field(..., description="Originating session ID")
    correlation_id: str = Field(..., description="Tracing correlation ID")
    title: str = Field(..., description="Plan title")
    description: str = Field(default="", description="Detailed plan description")
    steps: List[WorkflowStep] = Field(..., description="List of workflow steps")
    state: WorkflowState = Field(default=WorkflowState.DRAFT, description="Overall workflow state")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")

    @field_validator("steps")
    @classmethod
    def validate_steps_non_empty(cls, steps: List[WorkflowStep]) -> List[WorkflowStep]:
        if not steps:
            raise ValueError("WorkflowPlan must contain at least one step")
        return steps

    @model_validator(mode="after")
    def validate_plan_graph(self) -> "WorkflowPlan":
        step_ids = set()
        for step in self.steps:
            if step.step_id in step_ids:
                raise ValueError(f"Duplicate step_id detected: '{step.step_id}'")
            step_ids.add(step.step_id)

        # Check dependency references
        for step in self.steps:
            for dep in step.depends_on:
                if dep == step.step_id:
                    raise ValueError(f"Step '{step.step_id}' cannot depend on itself")
                if dep not in step_ids:
                    raise ValueError(f"Step '{step.step_id}' depends on non-existent step '{dep}'")

        # Cycle detection using Kahn's algorithm (topological sort)
        in_degree: Dict[str, int] = {s.step_id: 0 for s in self.steps}
        adj: Dict[str, List[str]] = defaultdict(list)

        for step in self.steps:
            for dep in step.depends_on:
                adj[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        queue = deque([s_id for s_id, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(self.steps):
            cycle_steps = [s_id for s_id, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Cyclic dependency detected among steps: {cycle_steps}")

        return self


class WorkflowResult(BaseModel):
    """Structured outcome of a workflow execution."""
    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="ID of executed workflow plan")
    session_id: str = Field(..., description="Associated session ID")
    correlation_id: str = Field(..., description="Correlation ID for audit trace")
    final_state: WorkflowState = Field(..., description="Final terminal or active state")
    step_results: Dict[str, Any] = Field(default_factory=dict, description="Mapping of step_id to step output/result")
    completed_steps: List[str] = Field(default_factory=list, description="IDs of successfully completed steps")
    failed_steps: List[str] = Field(default_factory=list, description="IDs of steps that failed")
    duration_seconds: float = Field(default=0.0, description="Total execution time in seconds")
    audit_events: List[EventEnvelope] = Field(default_factory=list, description="Immutable log of all audit events emitted")
    error: Optional[ErrorEnvelope] = Field(default=None, description="Populated if workflow terminated with error")


class WorkflowCheckpoint(BaseModel):
    """Snapshot of workflow execution state for recovery and resume.
    
    Guarantees:
    - Failed-step recovery restores completed steps without re-running them.
    - Captures step states, partial results, and idempotency cache.
    """
    model_config = ConfigDict(frozen=True)

    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique checkpoint ID")
    plan_id: str = Field(..., description="Associated workflow plan ID")
    session_id: str = Field(..., description="Associated session ID")
    correlation_id: str = Field(..., description="Tracing correlation ID")
    state: WorkflowState = Field(..., description="Workflow state when checkpoint was taken")
    step_states: Dict[str, StepStatus] = Field(default_factory=dict, description="State snapshot for each step")
    step_results: Dict[str, Any] = Field(default_factory=dict, description="Execution outputs of completed steps")
    completed_steps: List[str] = Field(default_factory=list, description="IDs of completed steps")
    failed_steps: List[str] = Field(default_factory=list, description="IDs of failed steps")
    idempotency_store: Dict[str, Any] = Field(default_factory=dict, description="Cached idempotency outputs")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of checkpoint")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational metadata or failure context")


class WorkflowProposal(BaseModel):
    """Proposal emitted from Reasoning (W3) to initiate a workflow.
    
    Bridges reasoning decisions into validated WorkflowPlan structures.
    """
    model_config = ConfigDict(frozen=True)

    proposal_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique proposal identifier")
    session_id: str = Field(..., description="Originating session identifier")
    correlation_id: str = Field(..., description="Correlation ID for end-to-end tracing")
    intent: str = Field(..., description="Detected user intent or recommended workflow goal")
    suggested_action: Optional[str] = Field(default=None, description="Action suggestion from reasoning engine")
    steps: List[WorkflowStep] = Field(default_factory=list, description="Proposed workflow steps")
    confidence: float = Field(default=1.0, description="Reasoning confidence score [0.0 - 1.0]")
    sources_used: List[Dict[str, Any]] = Field(default_factory=list, description="Context citations backing this proposal")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp proposal was formed")

