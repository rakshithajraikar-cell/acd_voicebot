"""Backend Approval Bridge (W4 <-> W5 Integration).

Provides a bridge between the W4 Agentic Workflow Engine and W5 Backend/Observability
services (Radhika B). Enables synchronizing human approval states, checking external
approval decisions, and publishing session audit trails.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sde6_voicebot.contracts.common import EventEnvelope
from sde6_voicebot.contracts.workflow import (
    ApprovalRequest,
    ApprovalStatus,
)


class BackendApprovalBridge:
    """Bridge for synchronizing approval state and audit records with W5 backend."""

    def __init__(self):
        self._backend_approval_store: Dict[str, ApprovalRequest] = {}
        self._session_audit_store: Dict[str, List[EventEnvelope]] = {}

    def register_approval_request(self, request: ApprovalRequest) -> None:
        """Register a new pending approval request from the workflow executor."""
        self._backend_approval_store[request.request_id] = request

    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Fetch the current approval request record from the backend store."""
        return self._backend_approval_store.get(request_id)

    def get_approval_state(self, request_id: str) -> Optional[ApprovalStatus]:
        """Query the current approval status for a request ID."""
        req = self._backend_approval_store.get(request_id)
        return req.status if req else None

    def update_backend_approval(
        self,
        request_id: str,
        status: ApprovalStatus,
        decided_by: str = "backend_system",
        rejection_reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Update an approval request with a backend or administrative decision."""
        req = self._backend_approval_store.get(request_id)
        if not req:
            raise KeyError(f"Approval request '{request_id}' not found in backend store")

        updated = ApprovalRequest(
            request_id=req.request_id,
            workflow_id=req.workflow_id,
            step_id=req.step_id,
            tool_name=req.tool_name,
            action_summary=req.action_summary,
            parameters=req.parameters,
            consequential_reason=req.consequential_reason,
            status=status,
            requested_at=req.requested_at,
            decided_at=datetime.now(timezone.utc),
            decided_by=decided_by,
            rejection_reason=rejection_reason,
            expires_at=req.expires_at,
            ttl_seconds=req.ttl_seconds,
        )
        self._backend_approval_store[request_id] = updated
        return updated

    def publish_audit_event(self, event: EventEnvelope) -> None:
        """Ingest and append an immutable workflow audit event to the backend session trace."""
        session_id = event.session_id
        if session_id not in self._session_audit_store:
            self._session_audit_store[session_id] = []
        self._session_audit_store[session_id].append(event)

    def get_session_audit_trail(self, session_id: str) -> List[EventEnvelope]:
        """Retrieve the complete audit trail for a session."""
        return list(self._session_audit_store.get(session_id, []))
