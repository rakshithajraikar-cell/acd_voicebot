"""
Envelope and Lifecycle Schemas
SDE 6 Voicebot — Engineering Standards (Section 8)

Defines the shared event envelope, error envelope, and lifecycle state machines
used across all workstreams (Audio, STT, Context & Reasoning, Workflow, Backend, Frontend).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
import datetime
import uuid


class SessionState(str, Enum):
    """
    Session lifecycle states.
    Constraints: Only transitions allowed by the backend state machine are valid.
    """
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class WorkflowState(str, Enum):
    """
    Workflow execution lifecycle states.
    Constraints: Consequential actions default to AWAITING_APPROVAL.
    """
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EventEnvelope:
    """
    Canonical Event Envelope for all inter-module communication.

    Fields:
    - event_id (str): Unique UUID v4 string identifying this event.
    - event_type (str): Dot-delimited event name (e.g. 'reasoning.completed', 'screen.frame_captured').
    - schema_version (str): Semantic version of the payload contract (e.g. '1.0.0').
    - session_id (str): UUID string of the active voicebot session.
    - correlation_id (str): UUID string linking related operations across modules.
    - timestamp (str): ISO 8601 UTC timestamp (e.g. '2026-10-31T12:00:00Z').
    - producer (str): Component or workstream generating the event (e.g. 'w3.reasoning_engine').
    - payload (Dict[str, Any]): Strongly-typed event-specific data dictionary.
    """
    event_id: str
    event_type: str
    schema_version: str
    session_id: str
    correlation_id: str
    timestamp: str
    producer: str
    payload: Dict[str, Any]

    @classmethod
    def create(
        cls,
        event_type: str,
        session_id: str,
        correlation_id: str,
        producer: str,
        payload: Dict[str, Any],
        schema_version: str = "1.0.0",
    ) -> EventEnvelope:
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            schema_version=schema_version,
            session_id=session_id,
            correlation_id=correlation_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            producer=producer,
            payload=payload,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "producer": self.producer,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EventEnvelope:
        return cls(
            event_id=str(data["event_id"]),
            event_type=str(data["event_type"]),
            schema_version=str(data.get("schema_version", "1.0.0")),
            session_id=str(data["session_id"]),
            correlation_id=str(data["correlation_id"]),
            timestamp=str(data["timestamp"]),
            producer=str(data["producer"]),
            payload=dict(data.get("payload", {})),
        )


@dataclass(frozen=True)
class ErrorEnvelope:
    """
    Canonical Error Envelope for safe error reporting.

    Fields:
    - code (str): Machine-readable uppercase snake_case error code (e.g. 'INSUFFICIENT_EVIDENCE', 'INVALID_SCHEMA').
    - message_safe_for_user (str): Human-readable error message scrubbed of sensitive info / stack traces.
    - retryable (bool): Flag indicating if client/caller may safely retry without modification.
    - correlation_id (str): UUID string linking this error to the original request.
    - details_redacted (Dict[str, Any]): Redacted debugging details containing no secrets or PII.
    """
    code: str
    message_safe_for_user: str
    retryable: bool
    correlation_id: str
    details_redacted: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message_safe_for_user": self.message_safe_for_user,
            "retryable": self.retryable,
            "correlation_id": self.correlation_id,
            "details_redacted": self.details_redacted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ErrorEnvelope:
        return cls(
            code=str(data["code"]),
            message_safe_for_user=str(data["message_safe_for_user"]),
            retryable=bool(data.get("retryable", False)),
            correlation_id=str(data.get("correlation_id", "")),
            details_redacted=dict(data.get("details_redacted", {})),
        )
