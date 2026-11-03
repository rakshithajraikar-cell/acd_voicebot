"""Audio Lifecycle Controller (SDE 6 - W1 - Days 10–11).

Manages the formal state machine for audio capture:
    CREATED -> RECORDING <-> PAUSED -> STOPPED

Enforces:
- Strict lifecycle transitions (rejects illegal calls with AudioError).
- Automatic buffer flush/release registration on stop.
- Thread-safe, observable state transitions.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, List, Optional
import threading

from src.audio.schemas import AudioError


class LifecycleState(str, Enum):
    """Permitted states for the audio capture lifecycle."""
    CREATED = "created"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"


class AudioLifecycleController:
    """Controls and validates the state lifecycle of an audio session.

    Valid transitions:
        CREATED   -> RECORDING  (start)
        RECORDING -> PAUSED     (pause)
        PAUSED    -> RECORDING  (resume)
        RECORDING -> STOPPED    (stop)
        PAUSED    -> STOPPED    (stop)
        CREATED   -> STOPPED    (stop / cancel)

    All invalid transitions raise AudioError with code ILLEGAL_LIFECYCLE_TRANSITION.
    """

    def __init__(self) -> None:
        self._state: LifecycleState = LifecycleState.CREATED
        self._lock = threading.RLock()
        self._stop_callbacks: List[Callable[[], None]] = []

    @property
    def state(self) -> LifecycleState:
        """Current lifecycle state."""
        with self._lock:
            return self._state

    def register_on_stop(self, callback: Callable[[], None]) -> None:
        """Register a cleanup hook (e.g. releasing buffer) invoked when capture stops."""
        with self._lock:
            self._stop_callbacks.append(callback)

    def start(self) -> LifecycleState:
        """Transition from CREATED to RECORDING."""
        with self._lock:
            if self._state != LifecycleState.CREATED:
                raise AudioError(
                    code="ILLEGAL_LIFECYCLE_TRANSITION",
                    message_safe_for_user=f"Cannot start audio capture from state '{self._state.value}'. Only 'created' is permitted.",
                    details={"current_state": self._state.value, "requested_transition": "start"},
                )
            self._state = LifecycleState.RECORDING
            return self._state

    def pause(self) -> LifecycleState:
        """Transition from RECORDING to PAUSED."""
        with self._lock:
            if self._state != LifecycleState.RECORDING:
                raise AudioError(
                    code="ILLEGAL_LIFECYCLE_TRANSITION",
                    message_safe_for_user=f"Cannot pause audio capture from state '{self._state.value}'. Only 'recording' is permitted.",
                    details={"current_state": self._state.value, "requested_transition": "pause"},
                )
            self._state = LifecycleState.PAUSED
            return self._state

    def resume(self) -> LifecycleState:
        """Transition from PAUSED back to RECORDING."""
        with self._lock:
            if self._state != LifecycleState.PAUSED:
                raise AudioError(
                    code="ILLEGAL_LIFECYCLE_TRANSITION",
                    message_safe_for_user=f"Cannot resume audio capture from state '{self._state.value}'. Only 'paused' is permitted.",
                    details={"current_state": self._state.value, "requested_transition": "resume"},
                )
            self._state = LifecycleState.RECORDING
            return self._state

    def stop(self) -> LifecycleState:
        """Transition to STOPPED and invoke stop callbacks (e.g., releasing buffer)."""
        with self._lock:
            if self._state == LifecycleState.STOPPED:
                # Already stopped: idempotent no-op or return state
                return self._state

            self._state = LifecycleState.STOPPED

            # Fire cleanup callbacks (e.g. buffer release)
            for cb in self._stop_callbacks:
                try:
                    cb()
                except Exception:
                    pass

            return self._state

    def can_capture(self) -> bool:
        """Check if incoming audio frames should be accepted and recorded."""
        with self._lock:
            return self._state == LifecycleState.RECORDING

    def is_active(self) -> bool:
        """Check if session has not yet stopped."""
        with self._lock:
            return self._state in (LifecycleState.RECORDING, LifecycleState.PAUSED)

    def reset(self) -> None:
        """Reset state machine back to CREATED (for reuse in mock runs)."""
        with self._lock:
            self._state = LifecycleState.CREATED
