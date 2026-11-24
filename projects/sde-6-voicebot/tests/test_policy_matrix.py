"""Tests for Policy Matrix (W4 Deliverable).

Verifies that the policy matrix enforces tool safety rules:
- Tool × Risk Level × Approval Required × Permission Scope
- Invariants:
  - Format notes is low risk and does not require approval.
  - Schedule reminder is medium risk and strictly requires approval.
  - Unknown tools are rejected with ToolSecurityError.
  - Missing scopes raise PermissionScopeError.
  - Timeouts exceeding maximum ceilings are rejected.
  - Unauthorized caller roles are blocked.
"""

import pytest

from sde6_voicebot.workflow.exceptions import (
    PermissionScopeError,
    ToolSecurityError,
    ToolArgumentError,
)
from sde6_voicebot.workflow.policy_matrix import (
    PolicyMatrix,
    PolicyRule,
    RiskLevel,
)
from sde6_voicebot.workflow.tools import (
    SCOPE_MEMORY_RW,
    SCOPE_NOTIFICATION_SCHEDULE,
)


class TestPolicyMatrix:
    @pytest.fixture
    def matrix(self) -> PolicyMatrix:
        return PolicyMatrix()

    def test_default_matrix_contains_all_allowlisted_tools(self, matrix):
        rules = matrix.list_rules()
        tool_names = {r.tool_name for r in rules}
        assert "format_notes" in tool_names
        assert "schedule_reminder" in tool_names
        assert len(rules) == 2

    def test_format_notes_policy_row(self, matrix):
        rule = matrix.get_rule("format_notes")
        assert rule.risk_level == RiskLevel.LOW
        assert rule.permission_scope == SCOPE_MEMORY_RW
        assert rule.requires_human_approval is False
        assert rule.is_idempotent is True
        assert rule.max_timeout_seconds == 30.0

    def test_schedule_reminder_policy_row(self, matrix):
        rule = matrix.get_rule("schedule_reminder")
        assert rule.risk_level == RiskLevel.MEDIUM
        assert rule.permission_scope == SCOPE_NOTIFICATION_SCHEDULE
        assert rule.requires_human_approval is True
        assert rule.is_idempotent is False
        assert rule.max_timeout_seconds == 30.0

    def test_unknown_tool_rejection(self, matrix):
        with pytest.raises(ToolSecurityError) as exc_info:
            matrix.get_rule("send_email")
        assert "send_email" in str(exc_info.value)

    def test_enforce_policy_missing_scope(self, matrix):
        with pytest.raises(PermissionScopeError) as exc_info:
            matrix.enforce_execution_policy(
                tool_name="format_notes",
                caller_role="user",
                granted_scopes=set(),  # empty scopes
                is_approved=True,
                timeout_seconds=10.0,
            )
        assert exc_info.value.required_scope == SCOPE_MEMORY_RW

    def test_enforce_policy_unapproved_consequential_tool(self, matrix):
        with pytest.raises(ToolSecurityError) as exc_info:
            matrix.enforce_execution_policy(
                tool_name="schedule_reminder",
                caller_role="user",
                granted_scopes={SCOPE_NOTIFICATION_SCHEDULE},
                is_approved=False,  # Unapproved!
                timeout_seconds=10.0,
            )
        assert "strictly requires human approval" in str(exc_info.value)

    def test_enforce_policy_unauthorized_caller_role(self, matrix):
        with pytest.raises(ToolSecurityError) as exc_info:
            matrix.enforce_execution_policy(
                tool_name="format_notes",
                caller_role="untrusted_external_guest",
                granted_scopes={SCOPE_MEMORY_RW},
                is_approved=True,
                timeout_seconds=10.0,
            )
        assert "not authorized" in str(exc_info.value)

    def test_enforce_policy_timeout_ceiling_exceeded(self, matrix):
        with pytest.raises(ToolArgumentError) as exc_info:
            matrix.enforce_execution_policy(
                tool_name="format_notes",
                caller_role="user",
                granted_scopes={SCOPE_MEMORY_RW},
                is_approved=True,
                timeout_seconds=120.0,  # Exceeds 30s ceiling!
            )
        assert "exceeds policy matrix ceiling" in str(exc_info.value)
