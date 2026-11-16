"""Audio module contracts, adapters, and stream processors (SDE 6 - W1).

Consolidated public API for:
- Week 1: Schemas (AudioChunk, AudioFormat, AudioError), MockMicrophoneSource, DeterministicAudioChunker.
- Week 2: Device adapters (AudioDevice, MockAudioDeviceAdapter, PermissionState),
          Lifecycle controller (AudioLifecycleController, LifecycleState),
          Voice activity detector (EnergyVAD, VADResult),
          Bounded audio buffer (BoundedAudioBuffer, BackpressurePolicy, BufferStats),
          Pipeline controller (AudioPipelineController).
"""

from src.audio.buffer import (
    BackpressurePolicy,
    BoundedAudioBuffer,
    BufferStats,
)
from src.audio.controller import AudioPipelineController
from src.audio.device import (
    AudioDevice,
    AudioDeviceAdapter,
    MockAudioDeviceAdapter,
    PermissionState,
)
from src.audio.lifecycle import (
    AudioLifecycleController,
    LifecycleState,
)
from src.audio.mock_source import (
    DeterministicAudioChunker,
    MockMicrophoneSource,
)
from src.audio.schemas import (
    AudioChunk,
    AudioError,
    AudioFormat,
    SUPPORTED_BIT_DEPTHS,
    SUPPORTED_SAMPLE_RATES,
)
from src.audio.vad import (
    EnergyVAD,
    VADResult,
    VoiceActivityDetector,
)

__all__ = [
    # Schemas
    "AudioChunk",
    "AudioError",
    "AudioFormat",
    "SUPPORTED_BIT_DEPTHS",
    "SUPPORTED_SAMPLE_RATES",
    # Mock source & chunker
    "DeterministicAudioChunker",
    "MockMicrophoneSource",
    # Device & Permissions
    "AudioDevice",
    "AudioDeviceAdapter",
    "MockAudioDeviceAdapter",
    "PermissionState",
    # Lifecycle
    "AudioLifecycleController",
    "LifecycleState",
    # VAD
    "EnergyVAD",
    "VADResult",
    "VoiceActivityDetector",
    # Buffer
    "BackpressurePolicy",
    "BoundedAudioBuffer",
    "BufferStats",
    # Controller
    "AudioPipelineController",
]
