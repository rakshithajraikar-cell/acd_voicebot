"""Unit tests for the Workflow State Machine.

Tests legal transitions, illegal transitions, terminal states, and history logging.
"""

import pytest

from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.workflow.exceptions import InvalidStateTransitionError
from sde6_voicebot.workflow.state_machine import WorkflowStateMachine


class TestWorkflowStateMachine:

    def test_initial_state_defaults_to_draft(self):
        sm = WorkflowStateMachine()
        assert sm.current_state == WorkflowState.DRAFT
        assert not sm.is_terminal

    def test_legal_happy_path_with_approval(self):
        """draft -> awaiting_approval -> running -> succeeded"""
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.AWAITING_APPROVAL, reason="Action needs approval")
        assert sm.current_state == WorkflowState.AWAITING_APPROVAL

        sm.transition_to(WorkflowState.RUNNING, reason="User approved")
        assert sm.current_state == WorkflowState.RUNNING

        sm.transition_to(WorkflowState.SUCCEEDED, reason="Completed successfully")
        assert sm.current_state == WorkflowState.SUCCEEDED
        assert sm.is_terminal

    def test_legal_direct_running_path(self):
        """draft -> running -> succeeded"""
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.RUNNING, reason="All harmless steps")
        assert sm.current_state == WorkflowState.RUNNING

        sm.transition_to(WorkflowState.SUCCEEDED, reason="Finished")
        assert sm.current_state == WorkflowState.SUCCEEDED

    def test_legal_pause_resume_cycle(self):
        """draft -> running -> paused -> running -> succeeded"""
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.RUNNING)
        sm.transition_to(WorkflowState.PAUSED, reason="User requested pause")
        assert sm.current_state == WorkflowState.PAUSED

        sm.transition_to(WorkflowState.RUNNING, reason="Resuming")
        assert sm.current_state == WorkflowState.RUNNING

        sm.transition_to(WorkflowState.SUCCEEDED)
        assert sm.current_state == WorkflowState.SUCCEEDED

    def test_legal_rejection_cancellation(self):
        """draft -> awaiting_approval -> cancelled"""
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.AWAITING_APPROVAL)
        sm.transition_to(WorkflowState.CANCELLED, reason="User rejected proposal")
        assert sm.current_state == WorkflowState.CANCELLED
        assert sm.is_terminal

    def test_legal_draft_cancellation(self):
        """draft -> cancelled"""
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.CANCELLED, reason="Cancelled before start")
        assert sm.current_state == WorkflowState.CANCELLED

    def test_legal_failure_transition(self):
        """draft -> running -> failed"""
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.RUNNING)
        sm.transition_to(WorkflowState.FAILED, reason="Step raised unexpected error")
        assert sm.current_state == WorkflowState.FAILED
        assert sm.is_terminal

    @pytest.mark.parametrize(
        "start_state,invalid_target",
        [
            # From DRAFT
            (WorkflowState.DRAFT, WorkflowState.SUCCEEDED),
            (WorkflowState.DRAFT, WorkflowState.FAILED),
            (WorkflowState.DRAFT, WorkflowState.PAUSED),
            # From AWAITING_APPROVAL
            (WorkflowState.AWAITING_APPROVAL, WorkflowState.DRAFT),
            (WorkflowState.AWAITING_APPROVAL, WorkflowState.PAUSED),
            (WorkflowState.AWAITING_APPROVAL, WorkflowState.SUCCEEDED),
            # From PAUSED
            (WorkflowState.PAUSED, WorkflowState.DRAFT),
            (WorkflowState.PAUSED, WorkflowState.AWAITING_APPROVAL),
            (WorkflowState.PAUSED, WorkflowState.SUCCEEDED),
            (WorkflowState.PAUSED, WorkflowState.FAILED),
            # Terminal states cannot transition to anything
            (WorkflowState.SUCCEEDED, WorkflowState.DRAFT),
            (WorkflowState.SUCCEEDED, WorkflowState.RUNNING),
            (WorkflowState.SUCCEEDED, WorkflowState.FAILED),
            (WorkflowState.SUCCEEDED, WorkflowState.CANCELLED),
            (WorkflowState.FAILED, WorkflowState.DRAFT),
            (WorkflowState.FAILED, WorkflowState.RUNNING),
            (WorkflowState.FAILED, WorkflowState.SUCCEEDED),
            (WorkflowState.CANCELLED, WorkflowState.DRAFT),
            (WorkflowState.CANCELLED, WorkflowState.RUNNING),
            (WorkflowState.CANCELLED, WorkflowState.SUCCEEDED),
        ],
    )
    def test_illegal_transitions_are_rejected(self, start_state, invalid_target):
        sm = WorkflowStateMachine(initial_state=start_state, correlation_id="test-corr")
        assert not sm.can_transition_to(invalid_target)
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            sm.transition_to(invalid_target)
        assert exc_info.value.current_state == start_state
        assert exc_info.value.target_state == invalid_target
        assert exc_info.value.correlation_id == "test-corr"

    def test_transition_history_logging(self):
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.RUNNING, reason="Started")
        sm.transition_to(WorkflowState.PAUSED, reason="Taking a break")
        sm.transition_to(WorkflowState.RUNNING, reason="Resumed")

        assert len(sm.history) == 3
        assert sm.history[0].from_state == WorkflowState.DRAFT
        assert sm.history[0].to_state == WorkflowState.RUNNING
        assert sm.history[1].to_state == WorkflowState.PAUSED
        assert sm.history[2].to_state == WorkflowState.RUNNING
