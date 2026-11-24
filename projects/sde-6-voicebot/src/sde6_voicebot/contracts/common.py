"""Common contracts and envelopes according to Section 8 engineering standards.

These schemas are defined once and reused throughout the project without duplication.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class SessionState(str, Enum):
    """Session lifecycle states."""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class WorkflowState(str, Enum):
    """Workflow execution states as mandated by Section 8 standards."""
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventEnvelope(BaseModel):
    """Standard event envelope contract for all inter-module and audit events.
    
    Fields follow Section 8:
    event_id, event_type, schema_version, session_id, correlation_id, timestamp, producer, payload.
    """
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()), description="Globally unique event ID")
    event_type: str = Field(..., description="Dot-separated event type string, e.g., 'workflow.step_started'")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    session_id: str = Field(..., description="Associated session ID")
    correlation_id: str = Field(..., description="Distributed tracing correlation ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of event creation")
    producer: str = Field(default="sde6.workflow_engine", description="Producing module / service identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Typed payload data for the event")


class ErrorEnvelope(BaseModel):
    """Standard error envelope contract safe for external/user presentation.
    
    Fields follow Section 8:
    code, message_safe_for_user, retryable, correlation_id, details_redacted.
    """
    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="Machine-readable error code, e.g., 'INVALID_PLAN_CYCLE'")
    message_safe_for_user: str = Field(..., description="Sanitized, user-friendly error message")
    retryable: bool = Field(default=False, description="Whether the operation can be safely retried")
    correlation_id: str = Field(..., description="Tracing correlation ID")
    details_redacted: Optional[str] = Field(default=None, description="Redacted internal debug info, free of secrets or PII")
