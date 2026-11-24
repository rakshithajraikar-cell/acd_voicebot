"""Workflow State Machine implementation.

Enforces legal state transitions among:
draft, awaiting_approval, running, paused, succeeded, failed, cancelled.
Terminal states: succeeded, failed, cancelled.
Rejects any illegal transitions with InvalidStateTransitionError.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set

from sde6_voicebot.contracts.common import WorkflowState
from sde6_voicebot.workflow.exceptions import InvalidStateTransitionError


@dataclass(frozen=True)
class StateTransitionRecord:
    """Audit record for a state transition."""
    from_state: WorkflowState
    to_state: WorkflowState
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowStateMachine:
    """Deterministic finite state machine for workflow lifecycles.
    
    Guarantees that:
    - Only documented, valid transitions are allowed.
    - Illegal transitions are rejected with InvalidStateTransitionError.
    - Terminal states cannot transition to any other state.
    - Transition history is preserved for audit trails.
    """

    # Formal transition rules table
    _VALID_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
        WorkflowState.DRAFT: {
            WorkflowState.AWAITING_APPROVAL,
            WorkflowState.RUNNING,
            WorkflowState.CANCELLED,
        },
        WorkflowState.AWAITING_APPROVAL: {
            WorkflowState.RUNNING,      # Approved
            WorkflowState.CANCELLED,    # Rejected or cancelled
            WorkflowState.FAILED,       # Expired or gate error
        },
        WorkflowState.RUNNING: {
            WorkflowState.PAUSED,
            WorkflowState.AWAITING_APPROVAL,  # Gated by a consequential step
            WorkflowState.SUCCEEDED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.PAUSED: {
            WorkflowState.RUNNING,      # Resumed
            WorkflowState.CANCELLED,    # Cancelled while paused
        },
        WorkflowState.SUCCEEDED: set(),  # Terminal state
        WorkflowState.FAILED: set(),     # Terminal state
        WorkflowState.CANCELLED: set(),  # Terminal state
    }

    _TERMINAL_STATES: Set[WorkflowState] = {
        WorkflowState.SUCCEEDED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    }

    def __init__(
        self,
        initial_state: WorkflowState = WorkflowState.DRAFT,
        correlation_id: str = "unknown",
        on_transition: Optional[Callable[[StateTransitionRecord], None]] = None,
    ):
        self._current_state = initial_state
        self._correlation_id = correlation_id
        self._on_transition = on_transition
        self._history: List[StateTransitionRecord] = []

    @property
    def current_state(self) -> WorkflowState:
        """Return the current workflow state."""
        return self._current_state

    @property
    def is_terminal(self) -> bool:
        """Check if the current state is terminal (succeeded, failed, cancelled)."""
        return self._current_state in self._TERMINAL_STATES

    @property
    def history(self) -> List[StateTransitionRecord]:
        """Return copy of state transition history."""
        return list(self._history)

    def can_transition_to(self, target_state: WorkflowState) -> bool:
        """Check whether a transition to target_state is legal from current_state."""
        allowed = self._VALID_TRANSITIONS.get(self._current_state, set())
        return target_state in allowed

    def transition_to(self, target_state: WorkflowState, reason: str = "") -> WorkflowState:
        """Transition the state machine to target_state if legal, or raise InvalidStateTransitionError.
        
        Args:
            target_state: Target WorkflowState
            reason: Contextual reason for the transition
            
        Returns:
            The new WorkflowState
            
        Raises:
            InvalidStateTransitionError: If the transition is not allowed.
        """
        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(
                current_state=self._current_state,
                target_state=target_state,
                correlation_id=self._correlation_id,
            )

        record = StateTransitionRecord(
            from_state=self._current_state,
            to_state=target_state,
            reason=reason or f"Transitioned from {self._current_state.value} to {target_state.value}",
        )
        self._current_state = target_state
        self._history.append(record)

        if self._on_transition:
            self._on_transition(record)

        return self._current_state
