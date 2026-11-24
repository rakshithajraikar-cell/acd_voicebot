"""Tests for invalid workflow plans, dependency cycle detection, and security rejections."""

import pytest
from pydantic import ValidationError

from sde6_voicebot.contracts.workflow import WorkflowPlan, WorkflowStep
from sde6_voicebot.workflow.exceptions import ToolSecurityError
from sde6_voicebot.workflow.executor import WorkflowExecutor


def test_reject_empty_steps():
    """Plan must contain at least one step."""
    with pytest.raises(ValidationError, match="at least one step"):
        WorkflowPlan(
            session_id="sess-1",
            correlation_id="corr-1",
            title="Empty Plan",
            steps=[],
        )


def test_reject_blank_step_id():
    """Step ID cannot be empty or whitespace."""
    with pytest.raises(ValidationError, match="step_id cannot be blank"):
        WorkflowStep(
            step_id="   ",
            name="Blank ID Step",
            tool_name="format_notes",
        )


def test_reject_duplicate_step_ids():
    """Plan must reject duplicate step IDs."""
    step1 = WorkflowStep(step_id="step-1", name="First", tool_name="format_notes", is_consequential=False)
    step2 = WorkflowStep(step_id="step-1", name="Duplicate", tool_name="format_notes", is_consequential=False)

    with pytest.raises(ValidationError, match="Duplicate step_id detected"):
        WorkflowPlan(
            session_id="sess-1",
            correlation_id="corr-1",
            title="Duplicate Steps Plan",
            steps=[step1, step2],
        )


def test_reject_self_dependency():
    """Step cannot depend on itself."""
    step = WorkflowStep(
        step_id="step-self",
        name="Self Dependent",
        tool_name="format_notes",
        depends_on=["step-self"],
        is_consequential=False,
    )
    with pytest.raises(ValidationError, match="cannot depend on itself"):
        WorkflowPlan(
            session_id="sess-1",
            correlation_id="corr-1",
            title="Self Dep Plan",
            steps=[step],
        )


def test_reject_non_existent_dependency():
    """Step cannot depend on a step ID that does not exist."""
    step = WorkflowStep(
        step_id="step-1",
        name="Valid",
        tool_name="format_notes",
        depends_on=["ghost-step-99"],
        is_consequential=False,
    )
    with pytest.raises(ValidationError, match="depends on non-existent step 'ghost-step-99'"):
        WorkflowPlan(
            session_id="sess-1",
            correlation_id="corr-1",
            title="Missing Dep Plan",
            steps=[step],
        )


def test_reject_two_step_cycle():
    """Cycle between 2 steps must be detected and rejected."""
    step_a = WorkflowStep(step_id="step-a", name="A", tool_name="format_notes", depends_on=["step-b"], is_consequential=False)
    step_b = WorkflowStep(step_id="step-b", name="B", tool_name="format_notes", depends_on=["step-a"], is_consequential=False)

    with pytest.raises(ValidationError, match="Cyclic dependency detected"):
        WorkflowPlan(
            session_id="sess-1",
            correlation_id="corr-1",
            title="2-Cycle Plan",
            steps=[step_a, step_b],
        )


def test_reject_multi_step_cycle():
    """Cycle across 3 steps: A -> B -> C -> A must be rejected."""
    step_a = WorkflowStep(step_id="step-a", name="A", tool_name="format_notes", depends_on=["step-c"], is_consequential=False)
    step_b = WorkflowStep(step_id="step-b", name="B", tool_name="format_notes", depends_on=["step-a"], is_consequential=False)
    step_c = WorkflowStep(step_id="step-c", name="C", tool_name="format_notes", depends_on=["step-b"], is_consequential=False)

    with pytest.raises(ValidationError, match="Cyclic dependency detected"):
        WorkflowPlan(
            session_id="sess-1",
            correlation_id="corr-1",
            title="3-Cycle Plan",
            steps=[step_a, step_b, step_c],
        )


def test_reject_non_allowlisted_tool_in_executor():
    """Executor must strictly reject plans referencing non-allowlisted tools."""
    bad_step = WorkflowStep(
        step_id="step-bad",
        name="Unauthorized Computer Action",
        tool_name="bash_eval",
        arguments={"cmd": "rm -rf /"},
        is_consequential=True,
    )
    plan = WorkflowPlan(
        session_id="sess-sec",
        correlation_id="corr-sec",
        title="Malicious Plan",
        steps=[bad_step],
    )

    executor = WorkflowExecutor()
    with pytest.raises(ToolSecurityError, match="non-allowlisted tool 'bash_eval'"):
        executor.start_workflow(plan)
