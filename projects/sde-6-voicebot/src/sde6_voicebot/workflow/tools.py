"""Allow-listed harmless mock tools and tool registry.

Safety guarantees:
- Exactly two harmless mock tools are implemented: 'format_notes' and 'schedule_reminder'.
- No unrestricted computer control, no external network requests, no subprocess calls.
- Strict allow-list enforcement: Any call to an unregistered or non-allowlisted tool is immediately rejected.
- Consequential tools default to is_consequential=True and require approval before execution.
"""

from typing import Any, Callable, Dict, Optional
from sde6_voicebot.contracts.workflow import ToolSpec
from sde6_voicebot.workflow.exceptions import ToolExecutionError, ToolSecurityError


def _execute_format_notes(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Harmless in-memory note formatter.
    
    Non-consequential: does not modify external state, disk, or network.
    """
    raw_text = arguments.get("text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ToolExecutionError("Argument 'text' must be a non-empty string", tool_name="format_notes")

    bullet_style = arguments.get("bullet_style", "dash")
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
    """
    title = arguments.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ToolExecutionError("Argument 'title' must be a non-empty string", tool_name="schedule_reminder")

    delay_minutes = arguments.get("delay_minutes")
    if not isinstance(delay_minutes, int) or delay_minutes <= 0:
        raise ToolExecutionError("Argument 'delay_minutes' must be a positive integer", tool_name="schedule_reminder")

    priority = arguments.get("priority", "normal")
    if priority not in {"low", "normal", "high"}:
        raise ToolExecutionError(f"Argument 'priority' must be one of ['low', 'normal', 'high'], got '{priority}'", tool_name="schedule_reminder")

    return {
        "status": "scheduled",
        "title": title.strip(),
        "delay_minutes": delay_minutes,
        "priority": priority,
        "mode": "mock_in_memory",
    }


# Tool 1: Harmless, non-consequential
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
    permission_scope="safe.memory.read_write",
    version="1.0.0",
)

# Tool 2: Harmless mock, but consequential (modifies schedule, triggers alert)
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
    permission_scope="user.notification.schedule",
    version="1.0.0",
)


class ToolRegistry:
    """Strict allow-list registry for harmless mock tools.
    
    Acceptance rule: Only the two harmless mock tools exist. No external sending or computer control.
    """

    ALLOWED_TOOL_NAMES = frozenset({"format_notes", "schedule_reminder"})

    def __init__(self):
        self._specs: Dict[str, ToolSpec] = {
            FORMAT_NOTES_SPEC.name: FORMAT_NOTES_SPEC,
            SCHEDULE_REMINDER_SPEC.name: SCHEDULE_REMINDER_SPEC,
        }
        self._executors: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            FORMAT_NOTES_SPEC.name: _execute_format_notes,
            SCHEDULE_REMINDER_SPEC.name: _execute_schedule_reminder,
        }

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

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an allow-listed tool with safety checks.
        
        Args:
            tool_name: Name of tool
            arguments: Dictionary of arguments
            
        Returns:
            Dict containing output result
            
        Raises:
            ToolSecurityError: If tool is not allow-listed
            ToolExecutionError: If arguments fail validation or execution encounters an error
        """
        if tool_name not in self._executors:
            raise ToolSecurityError(
                f"Security violation: Attempted execution of unapproved tool '{tool_name}'. "
                f"Allowed tools: {list(self.ALLOWED_TOOL_NAMES)}",
                tool_name=tool_name,
            )
        executor = self._executors[tool_name]
        return executor(arguments)
