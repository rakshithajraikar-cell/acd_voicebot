"""Comprehensive Unit Test Suite for Week 2 (SDE 6 - W1 - Days 8–14).

Verifies:
- Device selection, permission grant/denial states, and unsupported device formats.
- Lifecycle state transitions (CREATED, RECORDING, PAUSED, STOPPED) and rejection of illegal states.
- Buffer release on stop.
- Voice Activity Detection (VAD) with configurable thresholds, noise rejection, and hangover.
- Bounded audio buffer backpressure (DROP_OLDEST, DROP_NEWEST, REJECT) and dropped chunk telemetry.
- Detection of gaps and late chunks.
- Integrated AudioPipelineController flow in mock mode with zero hardware dependency.
"""

import pytest

from src.audio.buffer import BackpressurePolicy, BoundedAudioBuffer
from src.audio.controller import AudioPipelineController
from src.audio.device import (
    AudioDevice,
    MockAudioDeviceAdapter,
    PermissionState,
)
from src.audio.lifecycle import AudioLifecycleController, LifecycleState
from src.audio.mock_source import MockMicrophoneSource
from src.audio.schemas import AudioChunk, AudioError, AudioFormat
from src.audio.vad import EnergyVAD


# ==============================================================================
# 1. Device Selection & Permission Tests (Days 8–9)
# ==============================================================================

class TestDeviceAdapterAndPermissions:
    """Tests for device discovery, selection, permissions, and validation."""

    def test_default_device_discovery(self):
        adapter = MockAudioDeviceAdapter()
        devices = adapter.list_devices()
        assert len(devices) >= 2
        default_dev = adapter.get_default_device()
        assert default_dev.is_default
        assert default_dev.is_available

    def test_select_valid_device(self):
        adapter = MockAudioDeviceAdapter()
        dev = adapter.select_device("mock-mic-studio")
        assert dev.device_id == "mock-mic-studio"
        assert adapter.selected_device == dev

    def test_select_nonexistent_device_raises_error(self):
        adapter = MockAudioDeviceAdapter()
        with pytest.raises(AudioError) as exc_info:
            adapter.select_device("nonexistent-device")
        assert exc_info.value.code == "DEVICE_NOT_FOUND"

    def test_select_unavailable_device_raises_error(self):
        adapter = MockAudioDeviceAdapter()
        with pytest.raises(AudioError) as exc_info:
            adapter.select_device("mock-mic-offline")
        assert exc_info.value.code == "DEVICE_UNAVAILABLE"
        assert "unavailable" in exc_info.value.message_safe_for_user.lower()

    def test_permission_denial_raises_clean_error(self):
        adapter = MockAudioDeviceAdapter(permission_state=PermissionState.DENIED)
        fmt = AudioFormat(sample_rate_hz=16000, channels=1)

        with pytest.raises(AudioError) as exc_info:
            adapter.validate_device_for_format("mock-mic-default", fmt)
        assert exc_info.value.code == "PERMISSION_DENIED"
        assert "denied" in exc_info.value.message_safe_for_user.lower()

    def test_unsupported_device_format_raises_error(self):
        # Create a device that only supports 16kHz mono
        limited_device = AudioDevice(
            device_id="mic-limited",
            name="Limited Mic",
            supported_sample_rates=[16000],
            supported_channels=[1],
        )
        adapter = MockAudioDeviceAdapter(custom_devices=[limited_device])

        # Attempt 48kHz format
        fmt_48k = AudioFormat(sample_rate_hz=48000, channels=1)
        with pytest.raises(AudioError) as exc_info:
            adapter.validate_device_for_format("mic-limited", fmt_48k)
        assert exc_info.value.code == "UNSUPPORTED_DEVICE_FORMAT"


# ==============================================================================
# 2. Lifecycle State Machine Tests (Days 10–11)
# ==============================================================================

class TestAudioLifecycleController:
    """Tests for start, pause, resume, stop lifecycle state machine."""

    def test_normal_lifecycle_flow(self):
        ctrl = AudioLifecycleController()
        assert ctrl.state == LifecycleState.CREATED
        assert not ctrl.can_capture()

        # CREATED -> RECORDING
        ctrl.start()
        assert ctrl.state == LifecycleState.RECORDING
        assert ctrl.can_capture()

        # RECORDING -> PAUSED
        ctrl.pause()
        assert ctrl.state == LifecycleState.PAUSED
        assert not ctrl.can_capture()

        # PAUSED -> RECORDING
        ctrl.resume()
        assert ctrl.state == LifecycleState.RECORDING
        assert ctrl.can_capture()

        # RECORDING -> STOPPED
        ctrl.stop()
        assert ctrl.state == LifecycleState.STOPPED
        assert not ctrl.can_capture()
        assert not ctrl.is_active()

    def test_illegal_start_transitions(self):
        ctrl = AudioLifecycleController()
        ctrl.start()

        # Cannot start again while RECORDING
        with pytest.raises(AudioError) as exc_info:
            ctrl.start()
        assert exc_info.value.code == "ILLEGAL_LIFECYCLE_TRANSITION"

        ctrl.stop()
        # Cannot start once STOPPED
        with pytest.raises(AudioError) as exc_info:
            ctrl.start()
        assert exc_info.value.code == "ILLEGAL_LIFECYCLE_TRANSITION"

    def test_illegal_pause_and_resume_transitions(self):
        ctrl = AudioLifecycleController()

        # Cannot pause from CREATED
        with pytest.raises(AudioError) as exc_info:
            ctrl.pause()
        assert exc_info.value.code == "ILLEGAL_LIFECYCLE_TRANSITION"

        # Cannot resume from CREATED
        with pytest.raises(AudioError) as exc_info:
            ctrl.resume()
        assert exc_info.value.code == "ILLEGAL_LIFECYCLE_TRANSITION"

    def test_stop_triggers_callback(self):
        ctrl = AudioLifecycleController()
        ctrl.start()

        callback_called = False

        def cleanup_hook():
            nonlocal callback_called
            callback_called = True

        ctrl.register_on_stop(cleanup_hook)
        ctrl.stop()
        assert callback_called


# ==============================================================================
# 3. Voice Activity Detection (VAD) Tests (Days 10–11)
# ==============================================================================

class TestEnergyVAD:
    """Tests for VAD speech classification, noise spike rejection, and hangover."""

    def test_silence_detection(self):
        vad = EnergyVAD(energy_threshold=0.05)
        fmt = AudioFormat(sample_rate_hz=16000, channels=1)

        # 20ms silence chunk
        silence_chunk = AudioChunk(
            sequence_id=0,
            timestamp_ms=0.0,
            format=fmt,
            payload=b"\x00" * 640,
        )

        result = vad.process_chunk(silence_chunk)
        assert not result.is_speech
        assert result.state == "SILENCE"
        assert result.energy_rms == 0.0

    def test_sustained_speech_detection(self):
        # Speech with min duration 40ms (2 chunks of 20ms)
        vad = EnergyVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
        source = MockMicrophoneSource(
            chunk_duration_ms=20.0,
            frequency_hz=440.0,
            amplitude=0.5,
        )

        c0 = source.read_chunk()
        assert c0 is not None
        res0 = vad.process_chunk(c0)
        # First chunk reaches 20ms, below 40ms threshold -> candidate noise check
        assert res0.state == "CANDIDATE_NOISE_CHECK"
        assert not res0.is_speech

        c1 = source.read_chunk()
        assert c1 is not None
        res1 = vad.process_chunk(c1)
        # Second chunk reaches 40ms -> confirmed speech!
        assert res1.is_speech
        assert res1.state == "SPEECH"

    def test_short_noise_spike_rejection(self):
        # A single 20ms click should NOT trigger speech if min_speech_duration_ms is 60ms
        import struct
        vad = EnergyVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
        fmt = AudioFormat()

        # 1 loud click chunk (20ms) with high amplitude samples (e.g. 25000 / 32768 = ~0.76 RMS)
        loud_sample = struct.pack("<h", 25000)
        click_chunk = AudioChunk(
            sequence_id=0,
            timestamp_ms=0.0,
            format=fmt,
            payload=loud_sample * 320,
        )
        res_click = vad.process_chunk(click_chunk)
        assert not res_click.is_speech
        assert res_click.state == "CANDIDATE_NOISE_CHECK"

        # Followed immediately by silence
        silence_chunk = AudioChunk(
            sequence_id=1,
            timestamp_ms=20.0,
            format=fmt,
            payload=b"\x00" * 640,
        )
        res_silence = vad.process_chunk(silence_chunk)
        assert not res_silence.is_speech
        assert res_silence.state == "SILENCE"


# ==============================================================================
# 4. Bounded Buffer & Backpressure Tests (Days 12–13)
# ==============================================================================

class TestBoundedAudioBuffer:
    """Tests for bounded buffer backpressure policies, telemetry, and gap/late detection."""

    def test_backpressure_drop_oldest(self):
        fmt = AudioFormat()
        buffer = BoundedAudioBuffer(capacity=3, policy=BackpressurePolicy.DROP_OLDEST)

        # Push 5 chunks into capacity 3 buffer
        for i in range(5):
            chunk = AudioChunk(
                sequence_id=i,
                timestamp_ms=float(i * 20),
                format=fmt,
                payload=b"\x00" * 640,
            )
            buffer.push(chunk)

        stats = buffer.get_stats()
        assert stats.capacity == 3
        assert stats.current_size == 3
        assert stats.total_received == 5
        assert stats.total_dropped == 2  # Oldest 2 were dropped

        # Remaining should be chunks #2, #3, #4
        remaining = buffer.pop_all()
        assert [c.sequence_id for c in remaining] == [2, 3, 4]

    def test_backpressure_drop_newest(self):
        fmt = AudioFormat()
        buffer = BoundedAudioBuffer(capacity=3, policy=BackpressurePolicy.DROP_NEWEST)

        for i in range(5):
            chunk = AudioChunk(
                sequence_id=i,
                timestamp_ms=float(i * 20),
                format=fmt,
                payload=b"\x00" * 640,
            )
            buffer.push(chunk)

        stats = buffer.get_stats()
        assert stats.total_dropped == 2
        # Remaining should be initial chunks #0, #1, #2
        remaining = buffer.pop_all()
        assert [c.sequence_id for c in remaining] == [0, 1, 2]

    def test_backpressure_reject_overflow(self):
        fmt = AudioFormat()
        buffer = BoundedAudioBuffer(capacity=2, policy=BackpressurePolicy.REJECT)

        for i in range(2):
            buffer.push(AudioChunk(i, float(i * 20), fmt, b"\x00" * 640))

        # Third chunk should raise BUFFER_OVERFLOW
        with pytest.raises(AudioError) as exc_info:
            buffer.push(AudioChunk(2, 40.0, fmt, b"\x00" * 640))
        assert exc_info.value.code == "BUFFER_OVERFLOW"

    def test_gap_and_late_chunk_detection(self):
        fmt = AudioFormat()
        buffer = BoundedAudioBuffer(capacity=10)

        # Chunk 0
        buffer.push(AudioChunk(0, 0.0, fmt, b"\x00" * 640))

        # Chunk 3 (gap of 2 chunks: #1 and #2 missing)
        buffer.push(AudioChunk(3, 60.0, fmt, b"\x00" * 640))
        assert buffer.get_stats().gaps_detected == 2

        # Late arrival of Chunk 1
        buffer.push(AudioChunk(1, 20.0, fmt, b"\x00" * 640))
        assert buffer.get_stats().late_chunks_detected == 1

    def test_release_flushes_buffer(self):
        fmt = AudioFormat()
        buffer = BoundedAudioBuffer(capacity=5)
        buffer.push(AudioChunk(0, 0.0, fmt, b"\x00" * 640))
        buffer.push(AudioChunk(1, 20.0, fmt, b"\x00" * 640))

        released = buffer.release()
        assert len(released) == 2
        assert buffer.is_empty

        # Pushing into released buffer raises error
        with pytest.raises(AudioError) as exc_info:
            buffer.push(AudioChunk(2, 40.0, fmt, b"\x00" * 640))
        assert exc_info.value.code == "BUFFER_CLOSED"


# ==============================================================================
# 5. Integrated Audio Pipeline Controller Tests (Day 14)
# ==============================================================================

class TestAudioPipelineController:
    """End-to-end integration test of controller in mock mode."""

    def test_pipeline_controller_complete_flow(self):
        controller = AudioPipelineController(
            chunk_duration_ms=20.0,
            buffer_capacity=10,
        )

        # 1. Start pipeline
        controller.start()
        assert controller.lifecycle.state == LifecycleState.RECORDING

        # 2. Capture 5 steps
        captured = []
        for _ in range(5):
            step = controller.capture_step()
            assert step is not None
            chunk, vad_res = step
            captured.append(chunk)

        assert len(captured) == 5
        stats = controller.get_stats()
        assert stats.current_size == 5

        # 3. Pause
        controller.pause()
        assert controller.capture_step() is None

        # 4. Resume
        controller.resume()
        step = controller.capture_step()
        assert step is not None

        # 5. Stop (releases buffer)
        remaining = controller.stop()
        assert len(remaining) == 6
        assert controller.buffer.is_empty
