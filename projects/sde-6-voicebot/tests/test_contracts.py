"""Unit tests for Section 8 and W4 workflow contracts and schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from sde6_voicebot.contracts.common import (
    EventEnvelope,
    ErrorEnvelope,
    SessionState,
    WorkflowState,
)
from sde6_voicebot.contracts.workflow import (
    ApprovalRequest,
    ApprovalStatus,
    StepStatus,
    ToolSpec,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStep,
)


def test_session_and_workflow_states_conform_to_spec():
    """Verify state values strictly match Section 8 standards."""
    expected_session_states = {"created", "active", "paused", "stopping", "completed", "failed", "expired"}
    assert {s.value for s in SessionState} == expected_session_states

    expected_workflow_states = {"draft", "awaiting_approval", "running", "paused", "succeeded", "failed", "cancelled"}
    assert {s.value for s in WorkflowState} == expected_workflow_states


def test_event_envelope_fields_and_immutability():
    """Verify EventEnvelope has all required fields and is immutable."""
    event = EventEnvelope(
        event_type="workflow.tested",
        session_id="sess-100",
        correlation_id="corr-100",
        payload={"message": "hello"},
    )
    assert event.event_id is not None
    assert event.schema_version == "1.0.0"
    assert event.session_id == "sess-100"
    assert event.correlation_id == "corr-100"
    assert isinstance(event.timestamp, datetime)
    assert event.producer == "sde6.workflow_engine"
    assert event.payload == {"message": "hello"}

    with pytest.raises(ValidationError):
        event.event_type = "mutated"  # Frozen check


def test_error_envelope_fields_and_redaction():
    """Verify ErrorEnvelope has user-safe message and redaction capabilities."""
    err = ErrorEnvelope(
        code="UNAUTHORIZED_ACTION",
        message_safe_for_user="Action was safely denied.",
        retryable=False,
        correlation_id="corr-200",
        details_redacted="Internal reason: tool was not permitted.",
    )
    assert err.code == "UNAUTHORIZED_ACTION"
    assert err.message_safe_for_user == "Action was safely denied."
    assert err.retryable is False
    assert err.details_redacted == "Internal reason: tool was not permitted."


def test_tool_spec_and_consequential_default():
    """Verify ToolSpec definitions and defaults."""
    spec = ToolSpec(
        tool_id="tool.test",
        name="test_tool",
        description="A test tool",
        parameters_schema={"type": "object"},
        is_consequential=True,
    )
    assert spec.is_consequential is True
    assert spec.permission_scope == "safe.mock"


def test_workflow_step_defaults():
    """Verify WorkflowStep defaults is_consequential to True for safety."""
    step = WorkflowStep(
        step_id="step-1",
        name="Step 1",
        tool_name="format_notes",
    )
    assert step.is_consequential is True  # Consequential actions default to True!
    assert step.status == StepStatus.PENDING
    assert step.depends_on == []


def test_approval_request_schema():
    """Verify ApprovalRequest schema fields and status."""
    req = ApprovalRequest(
        workflow_id="wf-1",
        step_id="step-consequential",
        tool_name="schedule_reminder",
        action_summary="Schedule mock reminder",
        consequential_reason="Alters calendar notifications",
    )
    assert req.status == ApprovalStatus.PENDING
    assert req.decided_at is None
    assert req.decided_by is None
