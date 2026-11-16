"""Unit and Integration Tests for Audio Week 3 (SDE 6 - W1 - Days 15–21).

Tests cover:
- D15–16: Speech start/end and normalized audio events carrying session & correlation IDs
- D17–18: Device-loss recovery, exponential backoff, reconnect, and clean cancellation
- D19–20: Transcription bridge handoff, chunk ordering, gap detection, silence suppression,
          and false-trigger noise spike rejection
- D21: End-to-end audio pipeline to transcription receiver integration
"""

from __future__ import annotations

import struct
import time
import uuid
import pytest

from contracts.envelope import EventEnvelope
from src.audio.buffer import BackpressurePolicy
from src.audio.controller import AudioPipelineController
from src.audio.device import AudioDevice, MockAudioDeviceAdapter
from src.audio.device_recovery import DeviceRecoveryManager
from src.audio.events import (
    AudioEventFactory,
    AudioEventEmitter,
    AudioEventType,
)
from src.audio.mock_source import MockMicrophoneSource
from src.audio.schemas import AudioChunk, AudioError, AudioFormat
from src.audio.transcription_bridge import (
    MockTranscriptionReceiver,
    SpeechSegment,
    TranscriptionBridge,
)
from src.audio.vad import EnergyVAD, VADResult


class SequenceAudioSource:
    """Helper mock audio source yielding pre-configured AudioChunks."""

    def __init__(self, chunks: list[AudioChunk]) -> None:
        self.chunks = list(chunks)
        self._index = 0

    def read_chunk(self) -> AudioChunk | None:
        if self._index < len(self.chunks):
            chunk = self.chunks[self._index]
            self._index += 1
            return chunk
        return None

    def stop(self) -> None:
        pass


class TestAudioEventsAndEnvelope:
    """Tests for D15–16: Canonical event envelope generation and emission."""

    def test_audio_event_types_defined(self) -> None:
        """Verify all canonical audio event types are defined."""
        assert AudioEventType.SPEECH_STARTED.value == "audio.speech_started"
        assert AudioEventType.SPEECH_ENDED.value == "audio.speech_ended"
        assert AudioEventType.CHUNK_NORMALIZED.value == "audio.chunk_normalized"
        assert AudioEventType.DEVICE_LOST.value == "audio.device_lost"
        assert AudioEventType.DEVICE_RECONNECTED.value == "audio.device_reconnected"
        assert AudioEventType.CAPTURE_CANCELLED.value == "audio.cancelled"

    def test_create_speech_started_envelope(self) -> None:
        """Verify speech started envelope contains required fields and IDs."""
        session_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        envelope = AudioEventFactory.create_speech_started(
            session_id=session_id,
            correlation_id=correlation_id,
            timestamp_ms=100.5,
            sequence_id=5,
            energy_rms=0.152,
            device_id="mock-mic-default",
        )

        assert isinstance(envelope, EventEnvelope)
        assert envelope.event_type == "audio.speech_started"
        assert envelope.session_id == session_id
        assert envelope.correlation_id == correlation_id
        assert envelope.producer == "w1.audio_pipeline"
        assert envelope.payload["sequence_id"] == 5
        assert envelope.payload["device_id"] == "mock-mic-default"
        assert envelope.payload["energy_rms"] == 0.152

    def test_create_speech_ended_envelope(self) -> None:
        """Verify speech ended envelope contains timing and chunk counts."""
        session_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        envelope = AudioEventFactory.create_speech_ended(
            session_id=session_id,
            correlation_id=correlation_id,
            start_timestamp_ms=100.0,
            end_timestamp_ms=500.0,
            total_speech_duration_ms=400.0,
            speech_chunks_count=20,
        )

        assert isinstance(envelope, EventEnvelope)
        assert envelope.event_type == "audio.speech_ended"
        assert envelope.session_id == session_id
        assert envelope.correlation_id == correlation_id
        assert envelope.payload["start_timestamp_ms"] == 100.0
        assert envelope.payload["end_timestamp_ms"] == 500.0
        assert envelope.payload["total_speech_duration_ms"] == 400.0
        assert envelope.payload["speech_chunks_count"] == 20

    def test_create_chunk_normalized_envelope(self) -> None:
        """Verify chunk normalized envelope encapsulates chunk & VAD metrics."""
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        chunk = AudioChunk(
            sequence_id=1,
            timestamp_ms=20.0,
            format=fmt,
            payload=b"\x00\x00" * 320,
        )
        vad_result = VADResult(
            is_speech=False,
            confidence=0.95,
            energy_rms=0.001,
            speech_duration_ms=0.0,
            state="SILENCE",
        )

        envelope = AudioEventFactory.create_chunk_normalized(
            session_id="sess-1",
            correlation_id="corr-1",
            chunk=chunk,
            vad_result=vad_result,
        )

        assert envelope.event_type == "audio.chunk_normalized"
        assert envelope.session_id == "sess-1"
        assert envelope.correlation_id == "corr-1"
        assert envelope.payload["sequence_id"] == 1
        assert envelope.payload["payload_bytes"] == 640
        assert envelope.payload["is_speech"] is False
        assert envelope.payload["vad_state"] == "SILENCE"

    def test_audio_event_emitter_ordering_and_dispatch(self) -> None:
        """Verify thread-safe event emitter delivers events in chronological order."""
        emitter = AudioEventEmitter()
        received: list[EventEnvelope] = []

        emitter.subscribe(lambda evt: received.append(evt))

        e1 = AudioEventFactory.create_speech_started("s1", "c1", 10.0, 1, 0.2, "mock-mic-default")
        e2 = AudioEventFactory.create_speech_ended("s1", "c1", 10.0, 50.0, 40.0, 2)

        emitter.emit(e1)
        emitter.emit(e2)

        assert len(received) == 2
        assert received[0].event_type == "audio.speech_started"
        assert received[1].event_type == "audio.speech_ended"
        assert len(emitter.get_history()) == 2
        assert len(emitter.get_events_by_type("audio.speech_started")) == 1

        emitter.clear()
        assert len(emitter.get_history()) == 0


class TestDeviceRecoveryAndCancellation:
    """Tests for D17–18: Device loss recovery, backoff, and cancellation."""

    def test_successful_device_reconnect(self) -> None:
        """Verify recovery manager recovers upon reconnect and emits device_lost & reconnected."""
        adapter = MockAudioDeviceAdapter()
        emitter = AudioEventEmitter()
        recovery = DeviceRecoveryManager(adapter, emitter, max_retries=3, backoff_ms=5.0)

        # Simulate device loss
        recovered_dev = recovery.handle_device_loss(
            lost_device_id="mock-mic-default",
            session_id="sess-rec-1",
            correlation_id="corr-rec-1",
            timestamp_ms=100.0,
        )

        assert recovered_dev.device_id == "mock-mic-default"
        events = emitter.get_history()
        assert len(events) == 2
        assert events[0].event_type == "audio.device_lost"
        assert events[0].payload["device_id"] == "mock-mic-default"
        assert events[1].event_type == "audio.device_reconnected"
        assert events[1].payload["device_id"] == "mock-mic-default"
        assert events[1].payload["retry_count"] == 1

    def test_fallback_to_default_device_when_candidate_fails(self) -> None:
        """Verify recovery falls back to default device if candidate remains offline."""
        adapter = MockAudioDeviceAdapter()
        emitter = AudioEventEmitter()
        recovery = DeviceRecoveryManager(adapter, emitter, max_retries=2, backoff_ms=5.0)

        # "mock-mic-offline" is preconfigured in adapter as is_available=False
        recovered = recovery.handle_device_loss(
            lost_device_id="mock-mic-offline",
            session_id="sess-rec-2",
            correlation_id="corr-rec-2",
            timestamp_ms=200.0,
        )

        assert recovered.device_id == "mock-mic-default"
        events = emitter.get_history()
        assert events[0].event_type == "audio.device_lost"
        assert events[1].event_type == "audio.device_reconnected"
        assert events[1].payload["device_id"] == "mock-mic-default"

    def test_device_recovery_exhaustion_raises_clean_error(self) -> None:
        """Verify AudioError is raised with DEVICE_RECOVERY_FAILED when no device can recover."""
        adapter = MockAudioDeviceAdapter()
        adapter._devices = {
            "mock-mic-offline": AudioDevice(
                device_id="mock-mic-offline",
                name="Mock Disconnected Mic",
                is_default=True,
                is_available=False,
            )
        }

        emitter = AudioEventEmitter()
        recovery = DeviceRecoveryManager(adapter, emitter, max_retries=2, backoff_ms=2.0)

        with pytest.raises(AudioError) as exc_info:
            recovery.handle_device_loss(
                lost_device_id="mock-mic-offline",
                session_id="sess-fail",
                correlation_id="corr-fail",
                timestamp_ms=300.0,
            )

        assert exc_info.value.code == "DEVICE_RECOVERY_FAILED"
        assert "disconnected and could not be recovered" in exc_info.value.message_safe_for_user

    def test_clean_session_cancellation(self) -> None:
        """Verify session cancellation stops capture, releases buffer, and emits audio.cancelled."""
        controller = AudioPipelineController()
        controller.start()

        # Generate some chunks
        for _ in range(5):
            controller.capture_step()

        assert not controller.buffer.is_empty

        # Cancel
        flushed = controller.cancel(reason="Integration test user cancellation")

        assert len(flushed) > 0
        assert controller.buffer.is_empty
        assert not controller.lifecycle.can_capture()

        # Verify event was emitted
        cancelled_events = controller.event_emitter.get_events_by_type("audio.cancelled")
        assert len(cancelled_events) == 1
        assert cancelled_events[0].payload["reason"] == "Integration test user cancellation"
        assert cancelled_events[0].payload["flushed_chunks_count"] == len(flushed)


class TestTranscriptionBridgeIntegration:
    """Tests for D19–20: Audio-to-STT transcription bridge filter and mock receiver."""

    def test_transcription_bridge_end_to_end_handoff(self) -> None:
        """Verify speech start, speech chunks, and speech end hand off to transcription receiver."""
        mock_receiver = MockTranscriptionReceiver()
        bridge = TranscriptionBridge(receiver=mock_receiver.on_speech_segment)

        session_id = "test-session-123"
        correlation_id = "test-corr-456"

        # 1. Speech Started Event
        start_evt = AudioEventFactory.create_speech_started(
            session_id=session_id,
            correlation_id=correlation_id,
            timestamp_ms=1000.0,
            sequence_id=1,
            energy_rms=0.18,
            device_id="mock-mic-default",
        )
        bridge.handle_event(start_evt)

        # 2. Chunk Normalized Events (Speech chunks)
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        for seq in range(1, 4):
            chunk = AudioChunk(
                sequence_id=seq,
                timestamp_ms=1000.0 + (seq * 20.0),
                format=fmt,
                payload=b"\x10\x10" * 320,
            )
            vad_res = VADResult(
                is_speech=True,
                confidence=0.9,
                energy_rms=0.18,
                speech_duration_ms=seq * 20.0,
                state="SPEECH",
            )
            chunk_evt = AudioEventFactory.create_chunk_normalized(
                session_id=session_id,
                correlation_id=correlation_id,
                chunk=chunk,
                vad_result=vad_res,
            )
            bridge.handle_event(chunk_evt)

        # 3. Speech Ended Event
        end_evt = AudioEventFactory.create_speech_ended(
            session_id=session_id,
            correlation_id=correlation_id,
            start_timestamp_ms=1000.0,
            end_timestamp_ms=1060.0,
            total_speech_duration_ms=60.0,
            speech_chunks_count=3,
        )
        bridge.handle_event(end_evt)

        # Verify bridge handed off speech segment to mock STT receiver
        assert len(mock_receiver.received_segments) == 1
        segment = mock_receiver.received_segments[0]
        assert segment.session_id == session_id
        assert segment.correlation_id == correlation_id
        assert segment.is_completed is True
        assert bridge.speech_chunks_ingested == 3

        # Verify mock receiver generated transcript contract
        assert len(mock_receiver.transcripts) == 1
        t_entry = mock_receiver.transcripts[0]
        assert t_entry["is_final"] is True
        assert t_entry["chunk_count"] == 3
        assert t_entry["confidence"] > 0.9

    def test_transcription_bridge_silence_suppression(self) -> None:
        """Verify silence chunks are filtered out without creating speech segments."""
        mock_receiver = MockTranscriptionReceiver()
        bridge = TranscriptionBridge(receiver=mock_receiver.on_speech_segment)

        fmt = AudioFormat()
        for seq in range(1, 6):
            chunk = AudioChunk(
                sequence_id=seq,
                timestamp_ms=seq * 20.0,
                format=fmt,
                payload=b"\x00\x00" * 320,
            )
            vad_res = VADResult(
                is_speech=False,
                confidence=0.95,
                energy_rms=0.001,
                speech_duration_ms=0.0,
                state="SILENCE",
            )
            chunk_evt = AudioEventFactory.create_chunk_normalized("s", "c", chunk, vad_res)
            bridge.handle_event(chunk_evt)

        assert bridge.silence_chunks_skipped == 5
        assert bridge.speech_chunks_ingested == 0
        assert len(mock_receiver.received_segments) == 0

    def test_transcription_bridge_sequence_gap_detection(self) -> None:
        """Verify gap detection triggers when sequence numbers skip."""
        bridge = TranscriptionBridge()
        fmt = AudioFormat()

        c1 = AudioChunk(sequence_id=1, timestamp_ms=20.0, format=fmt, payload=b"\x00\x00"*320)
        c2 = AudioChunk(sequence_id=4, timestamp_ms=80.0, format=fmt, payload=b"\x00\x00"*320)

        vad_res = VADResult(
            is_speech=False,
            confidence=0.9,
            energy_rms=0.0,
            speech_duration_ms=0.0,
            state="SILENCE",
        )

        bridge.handle_event(AudioEventFactory.create_chunk_normalized("s", "c", c1, vad_res))
        assert bridge.gaps_detected == 0

        # Jump from seq 1 to seq 4 (missing 2 and 3 -> gap of 2)
        bridge.handle_event(AudioEventFactory.create_chunk_normalized("s", "c", c2, vad_res))
        assert bridge.gaps_detected == 2

    def test_transcription_bridge_false_trigger_rejection(self) -> None:
        """Verify short noise spikes (0 speech chunks) are rejected as false triggers."""
        mock_receiver = MockTranscriptionReceiver()
        bridge = TranscriptionBridge(receiver=mock_receiver.on_speech_segment)

        # Trigger speech start
        start_evt = AudioEventFactory.create_speech_started("s", "c", 100.0, 1, 0.1, "mock-mic-default")
        bridge.handle_event(start_evt)

        # Immediately emit speech ended with 0 speech chunks (noise spike)
        end_evt = AudioEventFactory.create_speech_ended("s", "c", 100.0, 105.0, 5.0, 0)
        bridge.handle_event(end_evt)

        assert bridge.false_triggers_rejected == 1
        assert len(mock_receiver.received_segments) == 0


class TestWeek3AudioPipelineIntegration:
    """Tests for D21: Full pipeline integration with events, recovery, and bridge."""

    def test_full_pipeline_speech_lifecycle_events(self) -> None:
        """Verify full capture session generates start, normalized, and end events with IDs."""
        receiver = MockTranscriptionReceiver()
        bridge = TranscriptionBridge(receiver=receiver.on_speech_segment)

        session_id = "voice-session-w3"
        correlation_id = "corr-turn-1"

        controller = AudioPipelineController(
            chunk_duration_ms=20.0,
            energy_threshold=0.05,
            min_speech_duration_ms=40.0,
            session_id=session_id,
            correlation_id=correlation_id,
            transcription_bridge=bridge,
        )

        controller.select_device("mock-mic-default")

        fmt = AudioFormat()
        silence_payload = b"\x00\x00" * 320
        speech_payload = struct.pack("<h", 25000) * 320

        # Build 3 silence chunks, 3 speech chunks, 2 silence chunks
        chunks = []
        seq = 0
        t = 0.0
        for _ in range(3):
            chunks.append(AudioChunk(sequence_id=seq, timestamp_ms=t, format=fmt, payload=silence_payload))
            seq += 1
            t += 20.0
        for _ in range(3):
            chunks.append(AudioChunk(sequence_id=seq, timestamp_ms=t, format=fmt, payload=speech_payload))
            seq += 1
            t += 20.0
        for _ in range(2):
            chunks.append(AudioChunk(sequence_id=seq, timestamp_ms=t, format=fmt, payload=silence_payload))
            seq += 1
            t += 20.0

        source = SequenceAudioSource(chunks)
        controller.start(source)

        for _ in range(8):
            step_res = controller.capture_step()
            assert step_res is not None

        controller.stop()

        # Check emitted events
        events = controller.event_emitter.get_history()
        event_types = [e.event_type for e in events]

        assert "audio.chunk_normalized" in event_types
        assert "audio.speech_started" in event_types
        assert "audio.speech_ended" in event_types

        # Verify all events maintain canonical session_id and correlation_id
        for evt in events:
            assert evt.session_id == session_id
            assert evt.correlation_id == correlation_id

        # Verify transcription handoff occurred
        assert len(receiver.transcripts) >= 1

    def test_pipeline_device_loss_simulation(self) -> None:
        """Verify pipeline recovers cleanly upon simulated device disconnect."""
        controller = AudioPipelineController(
            session_id="session-dev-loss",
            correlation_id="corr-dev-loss",
        )
        controller.start()

        # Disconnect active device
        new_device = controller.simulate_device_loss()
        assert new_device.is_available is True

        # Ensure events emitted
        lost_evts = controller.event_emitter.get_events_by_type("audio.device_lost")
        recon_evts = controller.event_emitter.get_events_by_type("audio.device_reconnected")

        assert len(lost_evts) == 1
        assert len(recon_evts) == 1
        assert lost_evts[0].session_id == "session-dev-loss"
        assert recon_evts[0].session_id == "session-dev-loss"

    def test_cli_week3_demo_execution(self, capsys) -> None:
        """Verify the interactive CLI demo runs without error and displays formatted output."""
        from src.cli.audio_week3_demo import run_week3_demo
        exit_code = run_week3_demo()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Week 3 Interactive Demonstration" in captured.out
        assert "Week 3 Audio Pipeline Demo Completed Successfully!" in captured.out
