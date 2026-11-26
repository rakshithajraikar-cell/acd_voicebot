"""Device-Loss Recovery, Reconnection & Session Cancellation (SDE 6 - W1 - Days 17–18).

Provides:
- DeviceRecoveryManager: Detects device disconnects mid-stream, executes bounded
  reconnect retries with exponential backoff without crashing, and falls back to
  default available devices if needed.
- Cancellation: Stops capture immediately and releases the audio buffer cleanly.
"""

from __future__ import annotations

import time
from typing import List, Optional

from src.audio.buffer import BoundedAudioBuffer
from src.audio.device import AudioDevice, MockAudioDeviceAdapter
from src.audio.events import AudioEventFactory, AudioEventEmitter
from src.audio.lifecycle import AudioLifecycleController
from src.audio.schemas import AudioChunk, AudioError


class DeviceRecoveryManager:
    """Orchestrates resilient device recovery upon sudden device loss or disconnects.

    Guarantees:
    - Bounded retries with backoff (avoids CPU spin / hanging).
    - Emits audio.device_lost and audio.device_reconnected events.
    - Gracefully halts with typed AudioError if recovery is impossible (no unhandled crash).
    - Handles safe cancellation releasing all buffered memory.
    """

    def __init__(
        self,
        device_adapter: MockAudioDeviceAdapter,
        event_emitter: AudioEventEmitter,
        max_retries: int = 3,
        backoff_ms: float = 20.0,
    ) -> None:
        self.device_adapter: MockAudioDeviceAdapter = device_adapter
        self.event_emitter: AudioEventEmitter = event_emitter
        self.max_retries: int = max_retries
        self.backoff_ms: float = backoff_ms

        self.reconnect_count: int = 0
        self.is_recovering: bool = False

    def handle_device_loss(
        self,
        lost_device_id: str,
        session_id: str,
        correlation_id: str,
        timestamp_ms: float,
        error_message: str = "Hardware audio input device was disconnected.",
    ) -> AudioDevice:
        """Handle a detected device disconnect and attempt clean recovery.

        Args:
            lost_device_id: ID of the disconnected device.
            session_id: Active session UUID.
            correlation_id: Request correlation UUID.
            timestamp_ms: Timestamp when disconnect was detected.
            error_message: Safe diagnostic description.

        Returns:
            The newly connected AudioDevice.

        Raises:
            AudioError: With code DEVICE_RECOVERY_FAILED if all reconnect attempts fail.
        """
        start_time = time.monotonic()
        self.is_recovering = True

        # 1. Emit audio.device_lost event
        lost_event = AudioEventFactory.create_device_lost(
            session_id=session_id,
            correlation_id=correlation_id,
            device_id=lost_device_id,
            error_message=error_message,
            timestamp_ms=timestamp_ms,
        )
        self.event_emitter.emit(lost_event)

        # 2. Bounded retry loop attempting to reconnect or fallback
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # First attempt to see if original device came back online
                candidate_dev = self.device_adapter.select_device(lost_device_id)
                if candidate_dev.is_available:
                    recovery_dur_ms = (time.monotonic() - start_time) * 1000.0
                    self.reconnect_count += 1
                    self.is_recovering = False

                    # Emit audio.device_reconnected
                    reconnected_event = AudioEventFactory.create_device_reconnected(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        device_id=candidate_dev.device_id,
                        recovery_duration_ms=recovery_dur_ms,
                        retry_count=attempt,
                    )
                    self.event_emitter.emit(reconnected_event)
                    return candidate_dev
            except AudioError as err:
                last_error = err

            # Try falling back to system default available device
            try:
                default_dev = self.device_adapter.get_default_device()
                if default_dev.is_available and default_dev.device_id != lost_device_id:
                    self.device_adapter.select_device(default_dev.device_id)
                    recovery_dur_ms = (time.monotonic() - start_time) * 1000.0
                    self.reconnect_count += 1
                    self.is_recovering = False

                    # Emit audio.device_reconnected on fallback
                    reconnected_event = AudioEventFactory.create_device_reconnected(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        device_id=default_dev.device_id,
                        recovery_duration_ms=recovery_dur_ms,
                        retry_count=attempt,
                    )
                    self.event_emitter.emit(reconnected_event)
                    return default_dev
            except Exception as exc:
                last_error = exc

            time.sleep((self.backoff_ms * (2 ** (attempt - 1))) / 1000.0)

        self.is_recovering = False
        raise AudioError(
            code="DEVICE_RECOVERY_FAILED",
            message_safe_for_user=(
                f"Audio input device '{lost_device_id}' disconnected and could not be recovered "
                f"after {self.max_retries} attempts."
            ),
            details={
                "lost_device_id": lost_device_id,
                "retries": self.max_retries,
                "last_error": str(last_error),
            },
        )

    def cancel(
        self,
        lifecycle: AudioLifecycleController,
        buffer: BoundedAudioBuffer,
        session_id: str,
        correlation_id: str,
        reason: str = "User cancelled session capture",
    ) -> List[AudioChunk]:
        """Cancel audio capture cleanly, release memory buffers, and emit cancellation event."""
        # Release the buffer and stop lifecycle
        flushed_chunks = buffer.release()
        lifecycle.stop()

        cancelled_event = AudioEventFactory.create_capture_cancelled(
            session_id=session_id,
            correlation_id=correlation_id,
            reason=reason,
            flushed_chunks_count=len(flushed_chunks),
        )
        self.event_emitter.emit(cancelled_event)

        return flushed_chunks

