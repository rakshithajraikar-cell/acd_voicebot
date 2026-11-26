"""CLI Demonstration for Audio Week 3: Events, Device Recovery & STT Handoff (SDE 6 - W1).

Demonstrates:
1. Speech start/end and normalized audio events wrapped in EventEnvelope with session & correlation IDs.
2. Gap detection, silence suppression, and false-trigger noise rejection.
3. Mid-session simulated device loss, exponential backoff, and clean reconnect.
4. Safe cancellation stopping capture and flushing bounded buffer.
5. End-to-end handoff to Mock Speech-to-Text (W2) receiver.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time
import uuid

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from contracts.envelope import EventEnvelope
from src.audio.buffer import BackpressurePolicy
from src.audio.controller import AudioPipelineController
from src.audio.device import AudioDevice, MockAudioDeviceAdapter
from src.audio.events import AudioEventFactory, AudioEventEmitter, AudioEventType
from src.audio.schemas import AudioChunk, AudioFormat
from src.audio.transcription_bridge import MockTranscriptionReceiver, TranscriptionBridge


def run_week3_demo(
    session_id: str | None = None,
    correlation_id: str | None = None,
) -> int:
    """Run full interactive Week 3 Audio demonstration."""
    session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    correlation_id = correlation_id or f"corr-{uuid.uuid4().hex[:8]}"

    print("=" * 72)
    print(" SDE 6 - W1: Audio & VAD (Week 3 Interactive Demonstration)")
    print(" Events, Device-Loss Recovery & Transcription Integration")
    print("=" * 72)
    print(f"Session ID     : {session_id}")
    print(f"Correlation ID : {correlation_id}")
    print("-" * 72)

    # 1. Initialize Mock Transcription Receiver (W2 contract) and Bridge
    receiver = MockTranscriptionReceiver()
    bridge = TranscriptionBridge(receiver=receiver.on_speech_segment)

    # 2. Initialize Controller
    adapter = MockAudioDeviceAdapter()
    controller = AudioPipelineController(
        chunk_duration_ms=20.0,
        energy_threshold=0.05,
        min_speech_duration_ms=40.0,
        device_adapter=adapter,
        session_id=session_id,
        correlation_id=correlation_id,
        transcription_bridge=bridge,
    )

    print("\n[STEP 1] Device Selection & Permissions Check")
    dev = controller.select_device("mock-mic-default")
    print(f"  Selected Device : {dev.name} ({dev.device_id})")
    print(f"  Status          : AVAILABLE (Format: 16000Hz, Mono, PCM 16-bit)")

    print("\n[STEP 2] Simulating Ingestion & VAD Event Generation")
    print("  Emitting 3 silence chunks, 4 speech chunks (tone), 3 silence chunks...")

    fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
    silence_payload = b"\x00\x00" * 320
    speech_payload = struct.pack("<h", 25000) * 320

    class CustomStreamSource:
        def __init__(self, raw_chunks: list[AudioChunk]) -> None:
            self.chunks = raw_chunks
            self.idx = 0
        def read_chunk(self) -> AudioChunk | None:
            if self.idx < len(self.chunks):
                c = self.chunks[self.idx]
                self.idx += 1
                return c
            return None
        def stop(self) -> None:
            pass

    test_chunks = []
    t = 0.0
    # 3 silence
    for i in range(3):
        test_chunks.append(AudioChunk(sequence_id=i, timestamp_ms=t, format=fmt, payload=silence_payload))
        t += 20.0
    # 4 speech
    for i in range(3, 7):
        test_chunks.append(AudioChunk(sequence_id=i, timestamp_ms=t, format=fmt, payload=speech_payload))
        t += 20.0
    # 3 silence
    for i in range(7, 10):
        test_chunks.append(AudioChunk(sequence_id=i, timestamp_ms=t, format=fmt, payload=silence_payload))
        t += 20.0

    controller.start(CustomStreamSource(test_chunks))

    for _ in range(10):
        res = controller.capture_step()
        if res:
            chunk, vad_res = res
            status_tag = "[SPEECH]" if vad_res.is_speech else "[SILENCE]"
            print(f"  Chunk #{chunk.sequence_id:02d} | Time: {chunk.timestamp_ms:5.1f}ms | Energy: {vad_res.energy_rms:0.4f} | State: {status_tag}")

    controller.stop()

    print("\n[STEP 3] Emitted Event Envelopes Verification")
    events = controller.event_emitter.get_history()
    print(f"  Total Envelopes Emitted : {len(events)}")
    for evt in events:
        if evt.event_type != AudioEventType.CHUNK_NORMALIZED.value:
            print(f"  -> Event: {evt.event_type:<24} | Sess: {evt.session_id[:8]}... | Corr: {evt.correlation_id[:8]}... | Payload: {evt.payload}")

    print("\n[STEP 4] Transcription Bridge Telemetry & W2 STT Handoff")
    print(f"  Silence Chunks Filtered  : {bridge.silence_chunks_skipped}")
    print(f"  Speech Chunks Ingested   : {bridge.speech_chunks_ingested}")
    print(f"  Gaps Detected            : {bridge.gaps_detected}")
    print(f"  False Triggers Rejected  : {bridge.false_triggers_rejected}")
    print(f"  Completed Speech Utterances : {len(receiver.received_segments)}")

    for idx, transcript in enumerate(receiver.transcripts, 1):
        print(f"  Transcript #{idx}: \"{transcript['transcript_text']}\" (Confidence: {transcript['confidence']}, Chunks: {transcript['chunk_count']})")

    print("\n[STEP 5] Mid-Session Hardware Loss & Reconnection Demo")
    print("  Simulating sudden microphone hardware disconnect...")
    new_dev = controller.simulate_device_loss()
    print(f"  Device Recovery Succeeded! Active device: {new_dev.name} ({new_dev.device_id})")
    loss_events = controller.event_emitter.get_events_by_type(AudioEventType.DEVICE_LOST.value)
    recon_events = controller.event_emitter.get_events_by_type(AudioEventType.DEVICE_RECONNECTED.value)
    print(f"  Emitted {len(loss_events)} audio.device_lost and {len(recon_events)} audio.device_reconnected envelopes.")

    print("\n[STEP 6] Clean Session Cancellation Demo")
    cancel_controller = AudioPipelineController(
        session_id=f"sess-cancel-{uuid.uuid4().hex[:6]}",
        correlation_id=f"corr-cancel-{uuid.uuid4().hex[:6]}",
    )
    cancel_controller.select_device("mock-mic-default")
    cancel_controller.start()
    for _ in range(4):
        cancel_controller.capture_step()
    print(f"  Buffer size before cancel: {cancel_controller.get_stats().current_size} chunks")
    flushed = cancel_controller.cancel(reason="User terminated interactive session")
    print(f"  Buffer flushed: {len(flushed)} chunks released. Capture stopped cleanly.")
    cancel_events = cancel_controller.event_emitter.get_events_by_type(AudioEventType.CAPTURE_CANCELLED.value)
    print(f"  Emitted: {cancel_events[-1].event_type} (Reason: '{cancel_events[-1].payload['reason']}')")

    print("\n" + "=" * 72)
    print(" Week 3 Audio Pipeline Demo Completed Successfully!")
    print("=" * 72)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 3 Audio Pipeline Interactive Demo")
    parser.add_argument("--session-id", type=str, default=None, help="Custom Session UUID")
    parser.add_argument("--correlation-id", type=str, default=None, help="Custom Correlation UUID")
    args = parser.parse_args()

    sys.exit(run_week3_demo(session_id=args.session_id, correlation_id=args.correlation_id))


if __name__ == "__main__":
    main()
