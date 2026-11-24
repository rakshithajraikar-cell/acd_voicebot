"""Formal Policy Matrix for Agentic Workflow Engine (W4).

Defines typed schemas and rules governing tool execution safety:
- Matrix dimensions: Tool Name × Risk Level × Approval Requirement × Permission Scope
- Enforces security invariants:
  1. Consequential tools (Risk >= MEDIUM) strictly require human approval.
  2. Tools without granted permission scopes are rejected.
  3. Non-idempotent tools cannot be retried.
  4. Timeouts must not exceed defined maximum limits.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, ConfigDict

from sde6_voicebot.workflow.exceptions import (
    PermissionScopeError,
    ToolSecurityError,
    ToolArgumentError,
)
from sde6_voicebot.workflow.tools import (
    SCOPE_MEMORY_RW,
    SCOPE_NOTIFICATION_SCHEDULE,
)


class RiskLevel(str, Enum):
    """Categorical risk classifications for tools."""
    LOW = "low"            # Read-only or safe in-memory data transformation
    MEDIUM = "medium"      # User notification, synthetic schedule modification
    HIGH = "high"          # Persistent data mutations, external API integrations
    CRITICAL = "critical"  # Financial, deletion, system modifications


class PolicyRule(BaseModel):
    """Specification of an execution policy governing a tool."""
    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(..., description="Canonical tool identifier")
    risk_level: RiskLevel = Field(..., description="Assigned risk rating")
    permission_scope: str = Field(..., description="Required OAuth/security permission scope")
    requires_human_approval: bool = Field(..., description="Whether human confirmation is mandatory")
    is_idempotent: bool = Field(..., description="Safe for automated bounded retry if True")
    max_timeout_seconds: float = Field(default=30.0, description="Upper bound on allowable execution timeout")
    allowed_caller_roles: List[str] = Field(
        default_factory=lambda: ["user", "system", "agent"],
        description="Authorized caller roles",
    )
    audit_logging_required: bool = Field(default=True, description="Audit record mandatory")


class PolicyMatrix:
    """Central policy engine and lookup matrix for workflow tool security."""

    DEFAULT_RULES: Dict[str, PolicyRule] = {
        "format_notes": PolicyRule(
            tool_name="format_notes",
            risk_level=RiskLevel.LOW,
            permission_scope=SCOPE_MEMORY_RW,
            requires_human_approval=False,
            is_idempotent=True,
            max_timeout_seconds=30.0,
            allowed_caller_roles=["user", "system", "agent"],
            audit_logging_required=True,
        ),
        "schedule_reminder": PolicyRule(
            tool_name="schedule_reminder",
            risk_level=RiskLevel.MEDIUM,
            permission_scope=SCOPE_NOTIFICATION_SCHEDULE,
            requires_human_approval=True,
            is_idempotent=False,
            max_timeout_seconds=30.0,
            allowed_caller_roles=["user", "system", "agent"],
            audit_logging_required=True,
        ),
    }

    def __init__(self, custom_rules: Optional[Dict[str, PolicyRule]] = None):
        self._rules: Dict[str, PolicyRule] = dict(self.DEFAULT_RULES)
        if custom_rules:
            self._rules.update(custom_rules)

    def get_rule(self, tool_name: str) -> PolicyRule:
        """Retrieve policy rule for a specific tool or raise ToolSecurityError."""
        if tool_name not in self._rules:
            raise ToolSecurityError(
                f"Tool '{tool_name}' not declared in security Policy Matrix",
                tool_name=tool_name,
            )
        return self._rules[tool_name]

    def list_rules(self) -> List[PolicyRule]:
        """Return all registered policy matrix rules."""
        return list(self._rules.values())

    def enforce_execution_policy(
        self,
        tool_name: str,
        caller_role: str,
        granted_scopes: Set[str],
        is_approved: bool,
        timeout_seconds: float,
        correlation_id: str = "unknown",
    ) -> PolicyRule:
        """Enforce all matrix dimensions before tool execution is allowed.
        
        Guarantees:
        - Unknown tools are rejected with ToolSecurityError.
        - Unauthorized caller roles are rejected with ToolSecurityError.
        - Missing permission scopes are rejected with PermissionScopeError.
        - Consequential tools requiring approval that have not been approved are rejected.
        - Timeouts exceeding max_timeout_seconds are rejected with ToolArgumentError.
        """
        rule = self.get_rule(tool_name)

        # 1. Caller Role Check
        if caller_role not in rule.allowed_caller_roles:
            raise ToolSecurityError(
                f"Caller role '{caller_role}' is not authorized to invoke tool '{tool_name}'. Allowed: {rule.allowed_caller_roles}",
                tool_name=tool_name,
                correlation_id=correlation_id,
            )

        # 2. Permission Scope Check
        if rule.permission_scope not in granted_scopes:
            raise PermissionScopeError(
                f"Execution context lacks required scope '{rule.permission_scope}' for tool '{tool_name}'",
                tool_name=tool_name,
                required_scope=rule.permission_scope,
                granted_scopes=granted_scopes,
                correlation_id=correlation_id,
            )

        # 3. Mandatory Human Approval Gate
        if rule.requires_human_approval and not is_approved:
            raise ToolSecurityError(
                f"Tool '{tool_name}' (Risk Level: {rule.risk_level.value.upper()}) strictly requires human approval before execution",
                tool_name=tool_name,
                correlation_id=correlation_id,
            )

        # 4. Timeout Bound Check
        if timeout_seconds > rule.max_timeout_seconds:
            raise ToolArgumentError(
                f"Requested timeout {timeout_seconds}s exceeds policy matrix ceiling of {rule.max_timeout_seconds}s for '{tool_name}'",
                tool_name=tool_name,
                correlation_id=correlation_id,
            )

        return rule
