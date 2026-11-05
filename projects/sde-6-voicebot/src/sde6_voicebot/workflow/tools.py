"""Allow-listed harmless mock tools and tool registry.

Safety guarantees:
- Exactly two harmless mock tools are implemented: 'format_notes' and 'schedule_reminder'.
- No unrestricted computer control, no external network requests, no subprocess calls.
- Strict allow-list enforcement: Any call to an unregistered or non-allowlisted tool is immediately rejected.
- Consequential tools default to is_consequential=True and require approval before execution.
- Idempotency is declared per tool; bounded retries are only permitted on idempotent operations.
- Permission scopes are strictly enforced before any execution occurs.
"""

from typing import Any, Callable, Dict, Optional, Set
from sde6_voicebot.contracts.workflow import ToolSpec
from sde6_voicebot.workflow.exceptions import (
    PermissionScopeError,
    ToolArgumentError,
    ToolExecutionError,
    ToolSecurityError,
)

# Standard mock permission scopes
SCOPE_MEMORY_RW = "safe.memory.read_write"
SCOPE_NOTIFICATION_SCHEDULE = "user.notification.schedule"
DEFAULT_SYSTEM_SCOPES = frozenset({SCOPE_MEMORY_RW, SCOPE_NOTIFICATION_SCHEDULE, "safe.mock"})


def _execute_format_notes(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Harmless in-memory note formatter.
    
    Non-consequential: does not modify external state, disk, or network.
    Idempotent: purely functional transformation of text.
    """
    raw_text = arguments.get("text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ToolArgumentError("Argument 'text' must be a non-empty string", tool_name="format_notes")

    bullet_style = arguments.get("bullet_style", "dash")
    if bullet_style not in {"dash", "star"}:
        raise ToolArgumentError(
            f"Argument 'bullet_style' must be one of ['dash', 'star'], got '{bullet_style}'",
            tool_name="format_notes",
        )

    symbol = "-" if bullet_style == "dash" else "*"
    cleaned_lines = [line.lstrip("-*• ").strip() for line in raw_text.splitlines() if line.strip()]
    formatted_lines = [f"{symbol} {line}" for line in cleaned_lines]
    formatted_output = "\n".join(formatted_lines)
    word_count = sum(len(line.split()) for line in cleaned_lines)

    return {
        "status": "success",
        "formatted_notes": formatted_output,
        "line_count": len(cleaned_lines),
        "word_count": word_count,
    }


def _execute_schedule_reminder(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synthetic in-memory reminder scheduler.
    
    Consequential: Gated action that schedules future user notification.
    Must never execute unapproved.
    Non-idempotent: Creating a reminder produces side effects.
    """
    title = arguments.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ToolArgumentError("Argument 'title' must be a non-empty string", tool_name="schedule_reminder")

    delay_minutes = arguments.get("delay_minutes")
    if not isinstance(delay_minutes, int) or isinstance(delay_minutes, bool) or delay_minutes <= 0:
        raise ToolArgumentError("Argument 'delay_minutes' must be a positive integer", tool_name="schedule_reminder")

    priority = arguments.get("priority", "normal")
    if priority not in {"low", "normal", "high"}:
        raise ToolArgumentError(
            f"Argument 'priority' must be one of ['low', 'normal', 'high'], got '{priority}'",
            tool_name="schedule_reminder",
        )

    return {
        "status": "scheduled",
        "title": title.strip(),
        "delay_minutes": delay_minutes,
        "priority": priority,
        "mode": "mock_in_memory",
    }


# Tool 1: Harmless, non-consequential, idempotent
FORMAT_NOTES_SPEC = ToolSpec(
    tool_id="tool.format_notes",
    name="format_notes",
    description="Safely formats raw text into standardized bulleted notes with statistics in memory.",
    parameters_schema={
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Raw text notes to format"},
            "bullet_style": {"type": "string", "enum": ["dash", "star"], "default": "dash"},
        },
    },
    is_consequential=False,
    is_idempotent=True,
    permission_scope=SCOPE_MEMORY_RW,
    version="1.0.0",
)

# Tool 2: Harmless mock, consequential, non-idempotent
SCHEDULE_REMINDER_SPEC = ToolSpec(
    tool_id="tool.schedule_reminder",
    name="schedule_reminder",
    description="Schedules a mock reminder in local memory. Consequential action requiring explicit user approval.",
    parameters_schema={
        "type": "object",
        "required": ["title", "delay_minutes"],
        "properties": {
            "title": {"type": "string", "description": "Title of the reminder"},
            "delay_minutes": {"type": "integer", "minimum": 1, "description": "Minutes from now"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"},
        },
    },
    is_consequential=True,
    is_idempotent=False,
    permission_scope=SCOPE_NOTIFICATION_SCHEDULE,
    version="1.0.0",
)


class ToolRegistry:
    """Strict allow-list registry for harmless mock tools.
    
    Acceptance rules:
    - Only harmless mock tools exist. No external sending or computer control.
    - All tools are checked against allow-list.
    - Argument validation rejects missing or malformed parameters.
    - Permission scopes are strictly enforced.
    - Idempotency metadata informs retry safety.
    """

    ALLOWED_TOOL_NAMES = frozenset({"format_notes", "schedule_reminder"})

    def __init__(self, granted_scopes: Optional[Set[str]] = None):
        self._specs: Dict[str, ToolSpec] = {
            FORMAT_NOTES_SPEC.name: FORMAT_NOTES_SPEC,
            SCHEDULE_REMINDER_SPEC.name: SCHEDULE_REMINDER_SPEC,
        }
        self._executors: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            FORMAT_NOTES_SPEC.name: _execute_format_notes,
            SCHEDULE_REMINDER_SPEC.name: _execute_schedule_reminder,
        }
        self._granted_scopes: Set[str] = set(granted_scopes) if granted_scopes is not None else set(DEFAULT_SYSTEM_SCOPES)

    @property
    def granted_scopes(self) -> Set[str]:
        """Return a copy of currently granted permission scopes."""
        return set(self._granted_scopes)

    def set_granted_scopes(self, scopes: Set[str]) -> None:
        """Update granted permission scopes for this registry session."""
        self._granted_scopes = set(scopes)

    def get_spec(self, tool_name: str) -> ToolSpec:
        """Retrieve the ToolSpec for an allow-listed tool."""
        if tool_name not in self._specs:
            raise ToolSecurityError(
                f"Unauthorized tool '{tool_name}'. Only allow-listed tools {list(self.ALLOWED_TOOL_NAMES)} are permitted.",
                tool_name=tool_name,
            )
        return self._specs[tool_name]

    def has_tool(self, tool_name: str) -> bool:
        """Check if tool is in the allow-list."""
        return tool_name in self._specs

    def list_specs(self) -> Dict[str, ToolSpec]:
        """Return all allow-listed ToolSpecs."""
        return dict(self._specs)

    def is_tool_idempotent(self, tool_name: str) -> bool:
        """Return whether the specified tool is marked idempotent."""
        spec = self.get_spec(tool_name)
        return spec.is_idempotent

    def validate_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """Validate input arguments against tool parameter constraints."""
        if not isinstance(arguments, dict):
            raise ToolArgumentError(
                f"Arguments for tool '{tool_name}' must be a dictionary, got {type(arguments).__name__}",
                tool_name=tool_name,
            )

        spec = self.get_spec(tool_name)
        required = spec.parameters_schema.get("required", [])
        for req_field in required:
            if req_field not in arguments:
                raise ToolArgumentError(
                    f"Missing required argument '{req_field}' for tool '{tool_name}'",
                    tool_name=tool_name,
                )

        # Tool-specific validation
        if tool_name == "format_notes":
            text = arguments.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ToolArgumentError("Argument 'text' must be a non-empty string", tool_name="format_notes")
            bullet_style = arguments.get("bullet_style")
            if bullet_style is not None and bullet_style not in {"dash", "star"}:
                raise ToolArgumentError(
                    f"Argument 'bullet_style' must be one of ['dash', 'star'], got '{bullet_style}'",
                    tool_name="format_notes",
                )
        elif tool_name == "schedule_reminder":
            title = arguments.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ToolArgumentError("Argument 'title' must be a non-empty string", tool_name="schedule_reminder")
            delay = arguments.get("delay_minutes")
            if not isinstance(delay, int) or isinstance(delay, bool) or delay <= 0:
                raise ToolArgumentError("Argument 'delay_minutes' must be a positive integer", tool_name="schedule_reminder")
            priority = arguments.get("priority")
            if priority is not None and priority not in {"low", "normal", "high"}:
                raise ToolArgumentError(
                    f"Argument 'priority' must be one of ['low', 'normal', 'high'], got '{priority}'",
                    tool_name="schedule_reminder",
                )

    def enforce_permission(
        self,
        tool_name: str,
        granted_scopes: Optional[Set[str]] = None,
        correlation_id: str = "unknown",
    ) -> None:
        """Enforce that caller has the required permission scope for tool execution.
        
        Raises:
            PermissionScopeError: If caller lacks the required scope.
        """
        spec = self.get_spec(tool_name)
        active_scopes = granted_scopes if granted_scopes is not None else self._granted_scopes
        if spec.permission_scope not in active_scopes:
            raise PermissionScopeError(
                f"Permission denied: Tool '{tool_name}' requires permission scope '{spec.permission_scope}', "
                f"but caller only holds {sorted(list(active_scopes))}",
                tool_name=tool_name,
                required_scope=spec.permission_scope,
                granted_scopes=active_scopes,
                correlation_id=correlation_id,
            )

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        granted_scopes: Optional[Set[str]] = None,
        correlation_id: str = "unknown",
    ) -> Dict[str, Any]:
        """Execute an allow-listed tool with security and argument validation.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Argument dictionary
            granted_scopes: Optional caller permission scopes (defaults to registry's scopes)
            correlation_id: Tracing correlation ID
            
        Returns:
            Dict containing output result
            
        Raises:
            ToolSecurityError: If tool is unauthorized
            PermissionScopeError: If required scope is missing
            ToolArgumentError: If arguments fail validation
            ToolExecutionError: If execution fails
        """
        if tool_name not in self._executors:
            raise ToolSecurityError(
                f"Security violation: Attempted execution of unapproved tool '{tool_name}'. "
                f"Allowed tools: {list(self.ALLOWED_TOOL_NAMES)}",
                tool_name=tool_name,
                correlation_id=correlation_id,
            )

        # Enforce permission scope
        self.enforce_permission(tool_name, granted_scopes=granted_scopes, correlation_id=correlation_id)

        # Enforce argument validation
        self.validate_arguments(tool_name, arguments)

        executor = self._executors[tool_name]
        try:
            return executor(arguments)
        except (ToolArgumentError, ToolExecutionError, ToolSecurityError):
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"Internal execution failure in tool '{tool_name}': {exc}",
                tool_name=tool_name,
                correlation_id=correlation_id,
            ) from exc
