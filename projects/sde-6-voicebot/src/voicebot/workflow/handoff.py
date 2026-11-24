"""
Workflow Proposal Handoff Adapter and Mock Receiver
SDE 6 Voicebot — Workstream W3 to W4 Integration (Week 3 / Days 19-20)
Student: Prathibhashree K

Implements:
1. Schema validation for WorkflowProposal and its constituent WorkflowStepProposals.
2. Canonical EventEnvelope generation (event_type="workflow.proposal_submitted").
3. Handoff interface to dispatch proposals to the W4 Agentic Workflow Engine.
4. Working mock workflow engine receiver that accepts proposals, checks allow-list policies,
   and verifies the approval gate.
5. ErrorEnvelope mapping on malformed or invalid proposal handoff attempts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import datetime
import uuid

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.envelope import EventEnvelope, ErrorEnvelope, WorkflowState
from contracts.workflow import WorkflowProposal, WorkflowStepProposal, WorkflowActionRisk
from contracts.context import SourceReference


class WorkflowHandoffError(Exception):
    """Raised when workflow proposal validation or dispatch fails."""
    def __init__(self, message: str, error_envelope: Optional[ErrorEnvelope] = None):
        super().__init__(message)
        self.error_envelope = error_envelope


# Allow-listed harmless mock tools (per Week 1-3 standards)
ALLOW_LISTED_TOOLS = {
    "calendar.add_event": {
        "description": "Add an academic lecture or reminder event to student calendar",
        "allowed_params": {"title", "start_time", "end_time", "location", "description"},
        "risk": WorkflowActionRisk.IDEMPOTENT_WRITE,
        "requires_approval": True,
    },
    "email.draft": {
        "description": "Draft an academic email to professor or advisor",
        "allowed_params": {"to", "subject", "body"},
        "risk": WorkflowActionRisk.CONSEQUENTIAL,
        "requires_approval": True,
    },
    "library.renew_book": {
        "description": "Request renewal for a borrowed textbook",
        "allowed_params": {"book_title", "isbn", "renewal_days"},
        "risk": WorkflowActionRisk.IDEMPOTENT_WRITE,
        "requires_approval": True,
    },
    "academic.export_grades": {
        "description": "Export student grades transcript to a structured document",
        "allowed_params": {"semester", "format"},
        "risk": WorkflowActionRisk.READ_ONLY,
        "requires_approval": False,
    },
}


def validate_workflow_proposal(proposal: Any) -> WorkflowProposal:
    """
    Validates that a proposed workflow adheres to the WorkflowProposal contract.
    Enforces non-negotiable rules:
    - Must be a valid WorkflowProposal instance.
    - Proposal ID, session ID, correlation ID, and goal must be non-empty strings.
    - Sources used must be non-empty (strict grounding requirement).
    - Every step must be allow-listed and have valid parameters.
    - Consequential actions MUST require explicit user approval.
    """
    if not isinstance(proposal, WorkflowProposal):
        raise WorkflowHandoffError(
            f"Object is not a WorkflowProposal instance (got {type(proposal).__name__}).",
            ErrorEnvelope(
                code="INVALID_PROPOSAL_TYPE",
                message_safe_for_user="Invalid workflow proposal payload.",
                retryable=False,
                correlation_id="",
            ),
        )

    if not proposal.proposal_id or not proposal.session_id or not proposal.correlation_id:
        raise WorkflowHandoffError(
            "WorkflowProposal missing mandatory identifiers (proposal_id, session_id, correlation_id).",
            ErrorEnvelope(
                code="MISSING_PROPOSAL_IDENTIFIERS",
                message_safe_for_user="Proposal rejected: missing session or correlation identifier.",
                retryable=False,
                correlation_id=proposal.correlation_id,
            ),
        )

    if not proposal.goal or not proposal.goal.strip():
        raise WorkflowHandoffError(
            "WorkflowProposal goal cannot be empty.",
            ErrorEnvelope(
                code="EMPTY_PROPOSAL_GOAL",
                message_safe_for_user="Proposal rejected: empty goal description.",
                retryable=False,
                correlation_id=proposal.correlation_id,
            ),
        )

    # Validate steps
    if not proposal.steps:
        raise WorkflowHandoffError(
            "WorkflowProposal must contain at least one step.",
            ErrorEnvelope(
                code="EMPTY_PROPOSAL_STEPS",
                message_safe_for_user="Proposal rejected: no action steps specified.",
                retryable=False,
                correlation_id=proposal.correlation_id,
            ),
        )

    for step in proposal.steps:
        if not isinstance(step, WorkflowStepProposal):
            raise WorkflowHandoffError(
                f"Step is not a WorkflowStepProposal: {step}",
                ErrorEnvelope(
                    code="INVALID_STEP_SCHEMA",
                    message_safe_for_user="Proposal rejected: step schema invalid.",
                    retryable=False,
                    correlation_id=proposal.correlation_id,
                ),
            )
        # Check tool allow-list
        if step.tool_name not in ALLOW_LISTED_TOOLS:
            raise WorkflowHandoffError(
                f"Tool '{step.tool_name}' is not in the allow-list. Permitted tools: {list(ALLOW_LISTED_TOOLS.keys())}",
                ErrorEnvelope(
                    code="UNAUTHORIZED_TOOL",
                    message_safe_for_user=f"Proposal rejected: unauthorized tool '{step.tool_name}'.",
                    retryable=False,
                    correlation_id=proposal.correlation_id,
                    details_redacted={"tool_name": step.tool_name},
                ),
            )

        # Enforce non-negotiable approval rule for consequential actions
        tool_spec = ALLOW_LISTED_TOOLS[step.tool_name]
        if tool_spec["risk"] == WorkflowActionRisk.CONSEQUENTIAL and not step.requires_approval:
            raise WorkflowHandoffError(
                f"Consequential action '{step.tool_name}' must require user approval.",
                ErrorEnvelope(
                    code="APPROVAL_REQUIRED_VIOLATION",
                    message_safe_for_user="Consequential actions cannot bypass user approval gates.",
                    retryable=False,
                    correlation_id=proposal.correlation_id,
                ),
            )

    return proposal


class MockWorkflowReceiver:
    """
    Mock recipient representing the W4 Agentic Workflow Engine.
    Receives proposals handed off from W3, validates them, and tracks state transitions.
    """

    def __init__(self):
        self.received_proposals: List[WorkflowProposal] = []
        self.received_events: List[EventEnvelope] = []
        self.execution_audit_log: List[Dict[str, Any]] = []

    def receive_proposal_event(self, envelope: EventEnvelope) -> Dict[str, Any]:
        """
        Ingests a proposal EventEnvelope from W3.
        Validates event structure and internal proposal schema.
        """
        if envelope.event_type != "workflow.proposal_submitted":
            raise ValueError(f"Unexpected event_type: {envelope.event_type}")

        self.received_events.append(envelope)
        proposal_dict = envelope.payload.get("proposal", {})
        proposal = WorkflowProposal.from_dict(proposal_dict)
        validated = validate_workflow_proposal(proposal)

        self.received_proposals.append(validated)

        # Record audit entry
        status = WorkflowState.AWAITING_APPROVAL if validated.requires_user_approval else WorkflowState.DRAFT
        audit_entry = {
            "proposal_id": validated.proposal_id,
            "session_id": validated.session_id,
            "correlation_id": validated.correlation_id,
            "goal": validated.goal,
            "status": status.value,
            "step_count": len(validated.steps),
            "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.execution_audit_log.append(audit_entry)

        return {
            "accepted": True,
            "proposal_id": validated.proposal_id,
            "workflow_state": status.value,
            "requires_approval": validated.requires_user_approval,
            "steps": len(validated.steps),
        }


class WorkflowHandoffClient:
    """
    Client used by Reasoning layer (W3) to dispatch schema-validated proposals
    to the downstream Workflow module (W4).
    """

    def __init__(self, receiver: Optional[MockWorkflowReceiver] = None):
        self.receiver = receiver or MockWorkflowReceiver()
        self.handoff_count: int = 0
        self.errors_count: int = 0

    def handoff_proposal(
        self,
        proposal: WorkflowProposal,
    ) -> EventEnvelope:
        """
        Validates the WorkflowProposal, wraps it in an EventEnvelope,
        and submits it to the workflow module receiver.

        Returns:
        - EventEnvelope: The transmitted event envelope with full audit metadata.

        Raises:
        - WorkflowHandoffError: If validation fails or the proposal is rejected.
        """
        self.handoff_count += 1

        # 1. Validate proposal schema strictly
        try:
            validated = validate_workflow_proposal(proposal)
        except WorkflowHandoffError as exc:
            self.errors_count += 1
            raise exc

        # 2. Construct canonical EventEnvelope
        envelope = EventEnvelope.create(
            event_type="workflow.proposal_submitted",
            session_id=validated.session_id,
            correlation_id=validated.correlation_id,
            producer="w3.context_reasoning",
            payload={
                "proposal": validated.to_dict(),
                "steps_summary": [
                    {
                        "step_number": s.step_number,
                        "tool": s.tool_name,
                        "description": s.description,
                        "requires_approval": s.requires_approval,
                    }
                    for s in validated.steps
                ],
                "grounding_sources_count": len(validated.sources_used),
            },
            schema_version="1.0.0",
        )

        # 3. Dispatch to workflow engine receiver
        receipt = self.receiver.receive_proposal_event(envelope)
        return envelope
