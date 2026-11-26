"""Integrated Audio Pipeline Controller (SDE 6 - W1 - Weeks 2 & 3).

Integrates:
- AudioDeviceAdapter (permissions & device validation)
- AudioLifecycleController (start/pause/resume/stop state machine)
- EnergyVAD (deterministic voice activity detection)
- BoundedAudioBuffer (bounded queue with backpressure & telemetry)
- MockMicrophoneSource (synthetic audio emitter)
- AudioEventEmitter & AudioEventFactory (canonical EventEnvelope generation)
- DeviceRecoveryManager (automatic recovery on device loss with backoff)
- TranscriptionBridge (audio-to-STT handoff filter with silence/noise rejection)
"""

from __future__ import annotations

import time
from typing import Any, Callable, List, Optional, Tuple
import uuid

from src.audio.buffer import BackpressurePolicy, BoundedAudioBuffer, BufferStats
from src.audio.device import AudioDevice, MockAudioDeviceAdapter, PermissionState
from src.audio.device_recovery import DeviceRecoveryManager
from src.audio.events import AudioEventFactory, AudioEventEmitter
from src.audio.lifecycle import AudioLifecycleController, LifecycleState
from src.audio.mock_source import MockMicrophoneSource
from src.audio.schemas import AudioChunk, AudioError, AudioFormat
from src.audio.transcription_bridge import TranscriptionBridge
from src.audio.vad import EnergyVAD, VADResult


class AudioPipelineController:
    """Integrated Audio Pipeline Controller (SDE 6 - W1 - Weeks 2 & 3)."""
    # Existing code ...
    
    def get_capture_state(self) -> str:
        """Return a simple string representing the current capture state.
        Values: "recording", "paused", "stopped".
        """
        state = self.lifecycle.state
        if state == LifecycleState.RECORDING:
            return "recording"
        if state == LifecycleState.PAUSED:
            return "paused"
        return "stopped"

    """Master controller orchestrating hardware permissions, lifecycle states,
    audio ingestion, VAD classification, bounded stream buffering, event emission,
    device recovery, and transcription handoff.
    """

    def __init__(
        self,
        audio_format: Optional[AudioFormat] = None,
        chunk_duration_ms: float = 20.0,
        buffer_capacity: int = 50,
        buffer_policy: BackpressurePolicy = BackpressurePolicy.DROP_OLDEST,
        energy_threshold: float = 0.05,
        min_speech_duration_ms: float = 60.0,
        device_adapter: Optional[MockAudioDeviceAdapter] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        event_emitter: Optional[AudioEventEmitter] = None,
        recovery_manager: Optional[DeviceRecoveryManager] = None,
        transcription_bridge: Optional[TranscriptionBridge] = None,
    ) -> None:
        self.format: AudioFormat = audio_format or AudioFormat()
        self.chunk_duration_ms: float = chunk_duration_ms

        # Session & Correlation identifiers
        self.session_id: str = session_id or str(uuid.uuid4())
        self.correlation_id: str = correlation_id or str(uuid.uuid4())

        # Device & Permission adapter
        self.device_adapter: MockAudioDeviceAdapter = (
            device_adapter or MockAudioDeviceAdapter()
        )

        # Event Emitter
        self.event_emitter: AudioEventEmitter = event_emitter or AudioEventEmitter()

        # Recovery Manager
        self.recovery_manager: DeviceRecoveryManager = (
            recovery_manager
            or DeviceRecoveryManager(
                device_adapter=self.device_adapter,
                event_emitter=self.event_emitter,
            )
        )

        # Transcription Bridge (optional downstream consumer)
        self.transcription_bridge: Optional[TranscriptionBridge] = transcription_bridge
        if self.transcription_bridge:
            self.event_emitter.subscribe(self.transcription_bridge.handle_event)

        # Lifecycle controller
        self.lifecycle: AudioLifecycleController = AudioLifecycleController()

        # Bounded buffer
        self.buffer: BoundedAudioBuffer = BoundedAudioBuffer(
            capacity=buffer_capacity,
            policy=buffer_policy,
        )

        # Wire buffer release to lifecycle stop
        self.lifecycle.register_on_stop(self._on_lifecycle_stop)

        # VAD classifier
        self.vad: EnergyVAD = EnergyVAD(
            energy_threshold=energy_threshold,
            min_speech_duration_ms=min_speech_duration_ms,
        )

        # Internal source (mock microphone)
        self._source: Optional[MockMicrophoneSource] = None

        # Speech state tracking for event transitions
        self._is_in_speech: bool = False
        self._speech_start_ms: float = 0.0
        self._speech_chunk_count: int = 0

    def _on_lifecycle_stop(self) -> None:
        """Handler fired when lifecycle enters STOPPED state."""
        if not self.buffer.is_empty and not self.buffer._is_closed:
            self.buffer.release()
        if self._source:
            self._source.stop()

    def select_device(self, device_id: str) -> AudioDevice:
        """Select an audio input device, validating format and permission."""
        self.device_adapter.validate_device_for_format(device_id, self.format)
        return self.device_adapter.select_device(device_id)

    def start(
        self,
        source: Optional[MockMicrophoneSource] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Start recording session after verifying device permissions."""
        if session_id:
            self.session_id = session_id
        if correlation_id:
            self.correlation_id = correlation_id

        self._is_in_speech = False
        self._speech_start_ms = 0.0
        self._speech_chunk_count = 0

        selected_dev = self.device_adapter.selected_device
        self.device_adapter.validate_device_for_format(selected_dev.device_id, self.format)

        self.lifecycle.start()
        self._source = source or MockMicrophoneSource(
            audio_format=self.format,
            chunk_duration_ms=self.chunk_duration_ms,
        )

    def pause(self) -> None:
        """Pause audio capture."""
        self.lifecycle.pause()

    def resume(self) -> None:
        """Resume audio capture."""
        self.lifecycle.resume()

    def stop(self) -> List[AudioChunk]:
        """Stop audio capture and release the buffer, returning any unread chunks."""
        # If active speech was in progress, emit speech_ended before stopping
        if self._is_in_speech:
            self._is_in_speech = False
            end_ms = self._speech_start_ms + (self._speech_chunk_count * self.chunk_duration_ms)
            speech_end_event = AudioEventFactory.create_speech_ended(
                session_id=self.session_id,
                correlation_id=self.correlation_id,
                start_timestamp_ms=self._speech_start_ms,
                end_timestamp_ms=end_ms,
                total_speech_duration_ms=self._speech_chunk_count * self.chunk_duration_ms,
                speech_chunks_count=self._speech_chunk_count,
            )
            self.event_emitter.emit(speech_end_event)
            self._speech_chunk_count = 0

        remaining_chunks = self.buffer.release()
        self.lifecycle.stop()
        return remaining_chunks

    def cancel(self, reason: str = "User cancelled session capture") -> List[AudioChunk]:
        """Cancel audio capture cleanly, release memory buffers, and emit cancellation event."""
        self._is_in_speech = False
        self._speech_chunk_count = 0
        return self.recovery_manager.cancel(
            lifecycle=self.lifecycle,
            buffer=self.buffer,
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            reason=reason,
        )

    def simulate_device_loss(self, device_id: Optional[str] = None) -> AudioDevice:
        """Trigger device recovery workflow upon sudden disconnection."""
        lost_id = device_id or self.device_adapter.selected_device.device_id
        now_ms = time.monotonic() * 1000.0
        return self.recovery_manager.handle_device_loss(
            lost_device_id=lost_id,
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            timestamp_ms=now_ms,
        )

    def capture_step(self) -> Optional[Tuple[AudioChunk, VADResult]]:
        """Simulate single step of audio generation, VAD, and buffer enqueue.

        Emits:
        - audio.chunk_normalized for each captured chunk.
        - audio.speech_started when speech onset is detected.
        - audio.speech_ended when speech offset is detected.

        Returns (chunk, vad_result) if active, or None if paused/stopped.
        """
        if not self.lifecycle.can_capture():
            return None

        if not self._source:
            return None

        chunk = self._source.read_chunk()
        if chunk is None:
            return None

        vad_result = self.vad.process_chunk(chunk)
        self.buffer.push(chunk)

        # Emit chunk normalized event
        chunk_event = AudioEventFactory.create_chunk_normalized(
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            chunk=chunk,
            vad_result=vad_result,
        )
        self.event_emitter.emit(chunk_event)

        # Detect speech state transitions
        if not self._is_in_speech and vad_result.is_speech:
            # Transition to SPEECH
            self._is_in_speech = True
            self._speech_start_ms = chunk.timestamp_ms
            self._speech_chunk_count = 1

            speech_start_event = AudioEventFactory.create_speech_started(
                session_id=self.session_id,
                correlation_id=self.correlation_id,
                timestamp_ms=chunk.timestamp_ms,
                sequence_id=chunk.sequence_id,
                energy_rms=vad_result.energy_rms,
                device_id=self.device_adapter.selected_device.device_id,
            )
            self.event_emitter.emit(speech_start_event)

        elif self._is_in_speech and not vad_result.is_speech:
            # Transition to SILENCE (speech ended)
            self._is_in_speech = False
            total_duration_ms = max(0.0, chunk.timestamp_ms - self._speech_start_ms)

            speech_end_event = AudioEventFactory.create_speech_ended(
                session_id=self.session_id,
                correlation_id=self.correlation_id,
                start_timestamp_ms=self._speech_start_ms,
                end_timestamp_ms=chunk.timestamp_ms,
                total_speech_duration_ms=total_duration_ms,
                speech_chunks_count=self._speech_chunk_count,
            )
            self.event_emitter.emit(speech_end_event)
            self._speech_chunk_count = 0

        elif self._is_in_speech and vad_result.is_speech:
            self._speech_chunk_count += 1

        return chunk, vad_result

    def read_chunk(self) -> Optional[AudioChunk]:
        """Read next available AudioChunk from bounded buffer."""
        return self.buffer.pop()

    def get_stats(self) -> BufferStats:
        """Retrieve buffer telemetry metrics."""
        return self.buffer.get_stats()
