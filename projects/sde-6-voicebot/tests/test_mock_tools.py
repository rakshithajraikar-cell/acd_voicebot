"""Unit tests for harmless mock tools and strict allow-list enforcement."""

import pytest

from sde6_voicebot.workflow.exceptions import ToolExecutionError, ToolSecurityError
from sde6_voicebot.workflow.tools import (
    FORMAT_NOTES_SPEC,
    SCHEDULE_REMINDER_SPEC,
    ToolRegistry,
)


def test_registry_contains_only_two_harmless_tools():
    """Safety rule: Only the two harmless mock tools exist in the registry."""
    registry = ToolRegistry()
    specs = registry.list_specs()
    assert set(specs.keys()) == {"format_notes", "schedule_reminder"}
    assert len(specs) == 2


def test_format_notes_spec_is_non_consequential():
    assert FORMAT_NOTES_SPEC.is_consequential is False
    assert FORMAT_NOTES_SPEC.name == "format_notes"


def test_schedule_reminder_spec_is_consequential():
    assert SCHEDULE_REMINDER_SPEC.is_consequential is True
    assert SCHEDULE_REMINDER_SPEC.name == "schedule_reminder"


def test_format_notes_execution_success():
    registry = ToolRegistry()
    raw = "Item one\n- Item two\n• Item three"
    res = registry.execute_tool("format_notes", {"text": raw, "bullet_style": "dash"})

    assert res["status"] == "success"
    assert "- Item one" in res["formatted_notes"]
    assert "- Item two" in res["formatted_notes"]
    assert "- Item three" in res["formatted_notes"]
    assert res["line_count"] == 3
    assert res["word_count"] == 6


def test_format_notes_rejects_empty_text():
    registry = ToolRegistry()
    with pytest.raises(ToolExecutionError, match="Argument 'text' must be a non-empty string"):
        registry.execute_tool("format_notes", {"text": ""})


def test_schedule_reminder_execution_success():
    registry = ToolRegistry()
    res = registry.execute_tool(
        "schedule_reminder",
        {"title": "Review architecture doc", "delay_minutes": 15, "priority": "high"},
    )
    assert res["status"] == "scheduled"
    assert res["title"] == "Review architecture doc"
    assert res["delay_minutes"] == 15
    assert res["priority"] == "high"
    assert res["mode"] == "mock_in_memory"


def test_schedule_reminder_rejects_invalid_delay():
    registry = ToolRegistry()
    with pytest.raises(ToolExecutionError, match="Argument 'delay_minutes' must be a positive integer"):
        registry.execute_tool("schedule_reminder", {"title": "Test", "delay_minutes": -5})


def test_schedule_reminder_rejects_invalid_priority():
    registry = ToolRegistry()
    with pytest.raises(ToolExecutionError, match="Argument 'priority' must be one of"):
        registry.execute_tool("schedule_reminder", {"title": "Test", "delay_minutes": 10, "priority": "urgent"})


def test_security_violation_for_unauthorized_tools():
    """Attempt to run any tool not in the allow-list raises ToolSecurityError."""
    registry = ToolRegistry()
    with pytest.raises(ToolSecurityError, match="Attempted execution of unapproved tool 'send_external_sms'"):
        registry.execute_tool("send_external_sms", {"to": "12345", "body": "hello"})
