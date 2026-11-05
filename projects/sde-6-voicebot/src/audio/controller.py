"""Integrated Audio Pipeline Controller (SDE 6 - W1 - Week 2).

Integrates:
- AudioDeviceAdapter (permissions & device validation)
- AudioLifecycleController (start/pause/resume/stop state machine)
- EnergyVAD (deterministic voice activity detection)
- BoundedAudioBuffer (bounded queue with backpressure & telemetry)
- MockMicrophoneSource (synthetic audio emitter)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.audio.buffer import BackpressurePolicy, BoundedAudioBuffer, BufferStats
from src.audio.device import AudioDevice, MockAudioDeviceAdapter, PermissionState
from src.audio.lifecycle import AudioLifecycleController, LifecycleState
from src.audio.mock_source import MockMicrophoneSource
from src.audio.schemas import AudioChunk, AudioError, AudioFormat
from src.audio.vad import EnergyVAD, VADResult


class AudioPipelineController:
    """Master controller orchestrating hardware permissions, lifecycle states,

    audio ingestion, VAD classification, and bounded stream buffering.
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
    ) -> None:
        self.format: AudioFormat = audio_format or AudioFormat()
        self.chunk_duration_ms: float = chunk_duration_ms

        # Device & Permission adapter
        self.device_adapter: MockAudioDeviceAdapter = (
            device_adapter or MockAudioDeviceAdapter()
        )

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

    def start(self, source: Optional[MockMicrophoneSource] = None) -> None:
        """Start recording session after verifying device permissions."""
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
        remaining_chunks = self.buffer.release()
        self.lifecycle.stop()
        return remaining_chunks

    def capture_step(self) -> Optional[Tuple[AudioChunk, VADResult]]:
        """Simulate single step of audio generation, VAD, and buffer enqueue.

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

        return chunk, vad_result

    def read_chunk(self) -> Optional[AudioChunk]:
        """Read next available AudioChunk from bounded buffer."""
        return self.buffer.pop()

    def get_stats(self) -> BufferStats:
        """Retrieve buffer telemetry metrics."""
        return self.buffer.get_stats()
