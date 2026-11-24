"""Exceptions for the workflow engine."""

from typing import Optional, Set
from sde6_voicebot.contracts.common import WorkflowState, ErrorEnvelope


class WorkflowEngineError(Exception):
    """Base exception for all workflow engine errors."""

    def __init__(self, message: str, code: str = "WORKFLOW_ENGINE_ERROR", correlation_id: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.code = code
        self.correlation_id = correlation_id

    def to_error_envelope(self, retryable: bool = False) -> ErrorEnvelope:
        return ErrorEnvelope(
            code=self.code,
            message_safe_for_user=self.message,
            retryable=retryable,
            correlation_id=self.correlation_id,
            details_redacted=str(self),
        )


class InvalidStateTransitionError(WorkflowEngineError):
    """Raised when an illegal transition is attempted in the workflow state machine."""

    def __init__(self, current_state: WorkflowState, target_state: WorkflowState, correlation_id: str = "unknown"):
        message = f"Illegal workflow state transition from '{current_state.value}' to '{target_state.value}'"
        super().__init__(message, code="ILLEGAL_STATE_TRANSITION", correlation_id=correlation_id)
        self.current_state = current_state
        self.target_state = target_state


class InvalidPlanError(WorkflowEngineError):
    """Raised when a workflow plan fails validation (cycles, unknown dependencies, missing fields)."""

    def __init__(self, message: str, correlation_id: str = "unknown"):
        super().__init__(message, code="INVALID_WORKFLOW_PLAN", correlation_id=correlation_id)


class ToolExecutionError(WorkflowEngineError):
    """Raised when a harmless mock tool encounters an execution error."""

    def __init__(self, message: str, tool_name: str, correlation_id: str = "unknown"):
        super().__init__(message, code="TOOL_EXECUTION_FAILURE", correlation_id=correlation_id)
        self.tool_name = tool_name


class ToolSecurityError(WorkflowEngineError):
    """Raised when an unauthorized or non-allowlisted tool execution is attempted."""

    def __init__(self, message: str, tool_name: str, correlation_id: str = "unknown"):
        super().__init__(message, code="UNAUTHORIZED_TOOL_ATTEMPT", correlation_id=correlation_id)
        self.tool_name = tool_name


class PermissionScopeError(ToolSecurityError):
    """Raised when the execution context lacks the required permission scope for a tool."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        required_scope: str,
        granted_scopes: Optional[Set[str]] = None,
        correlation_id: str = "unknown",
    ):
        super().__init__(message, tool_name=tool_name, correlation_id=correlation_id)
        self.code = "PERMISSION_SCOPE_DENIED"
        self.required_scope = required_scope
        self.granted_scopes = granted_scopes or set()


class ToolArgumentError(ToolExecutionError):
    """Raised when tool arguments fail parameter schema or type validation."""

    def __init__(self, message: str, tool_name: str, correlation_id: str = "unknown"):
        super().__init__(message, tool_name=tool_name, correlation_id=correlation_id)
        self.code = "INVALID_TOOL_ARGUMENTS"


class ApprovalExpiredError(WorkflowEngineError):
    """Raised when an approval request has expired and cannot be approved."""

    def __init__(self, message: str, request_id: str = "unknown", correlation_id: str = "unknown"):
        super().__init__(message, code="APPROVAL_EXPIRED", correlation_id=correlation_id)
        self.request_id = request_id


class WorkflowTimeoutError(WorkflowEngineError):
    """Raised when step execution or tool invocation exceeds the configured timeout."""

    def __init__(self, message: str, step_id: str = "unknown", timeout_seconds: float = 0.0, correlation_id: str = "unknown"):
        super().__init__(message, code="WORKFLOW_TIMEOUT", correlation_id=correlation_id)
        self.step_id = step_id
        self.timeout_seconds = timeout_seconds


class DuplicateApprovalError(WorkflowEngineError):
    """Raised when an approval submission is received for an already decided request."""

    def __init__(self, message: str, request_id: str = "unknown", correlation_id: str = "unknown"):
        super().__init__(message, code="DUPLICATE_APPROVAL_SUBMISSION", correlation_id=correlation_id)
        self.request_id = request_id


class WorkflowCancelledError(WorkflowEngineError):
    """Raised when an operation is attempted on an already cancelled workflow."""

    def __init__(self, message: str, correlation_id: str = "unknown"):
        super().__init__(message, code="WORKFLOW_CANCELLED", correlation_id=correlation_id)
