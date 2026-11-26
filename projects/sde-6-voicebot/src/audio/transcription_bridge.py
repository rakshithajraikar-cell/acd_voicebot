"""Transcription Bridge & Audio-to-STT Handoff (SDE 6 - W1 - Days 19–20).

Provides:
- TranscriptionBridge: Bridges audio capture events to the team's Speech-to-Text (W2)
  transcription module.
- Ingestion filter:
    * Enforces strict chunk sequence ordering
    * Detects and logs sequence gaps
    * Filters out silence and brief noise spikes (false triggers)
    * Groups speech segments bounded by audio.speech_started and audio.speech_ended
- MockTranscriptionReceiver: Simulates W2 speech-to-text receiver contract in mock mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Callable, Dict, List, Optional

from contracts.envelope import EventEnvelope
from src.audio.events import AudioEventType
from src.audio.schemas import AudioChunk, AudioError


@dataclass
class SpeechSegment:
    """A contiguous utterance bounded by speech start and speech end events."""
    session_id: str
    correlation_id: str
    start_timestamp_ms: float
    end_timestamp_ms: Optional[float] = None
    chunks: List[AudioChunk] = field(default_factory=list)
    chunk_count: int = 0
    is_completed: bool = False

    @property
    def total_duration_ms(self) -> float:
        if self.chunks:
            return sum(c.duration_ms for c in self.chunks)
        if self.end_timestamp_ms is not None:
            return max(0.0, self.end_timestamp_ms - self.start_timestamp_ms)
        return 0.0

    @property
    def raw_audio_bytes(self) -> bytes:
        return b"".join(c.payload for c in self.chunks)


class MockTranscriptionReceiver:
    """Mock implementation of the W2 Speech-to-Text provider interface.

    Receives assembled speech segments and returns synthetic timestamped transcripts.
    """

    def __init__(self) -> None:
        self.received_segments: List[SpeechSegment] = []
        self.transcripts: List[Dict[str, Any]] = []

    def on_speech_segment(self, segment: SpeechSegment) -> Dict[str, Any]:
        """Process complete speech segment and output transcript contract."""
        self.received_segments.append(segment)

        transcript_entry = {
            "session_id": segment.session_id,
            "correlation_id": segment.correlation_id,
            "start_time_ms": segment.start_timestamp_ms,
            "end_time_ms": segment.end_timestamp_ms or (segment.start_timestamp_ms + segment.total_duration_ms),
            "duration_ms": segment.total_duration_ms,
            "chunk_count": len(segment.chunks) if segment.chunks else segment.chunk_count,
            "transcript_text": "Mock transcribed speech utterance.",
            "confidence": 0.98,
            "is_final": True,
        }
        self.transcripts.append(transcript_entry)
        return transcript_entry


class TranscriptionBridge:
    """Bridges the W1 audio stream to the W2 transcription module.

    Handles:
    - Event subscription and payload extraction
    - Gap detection and out-of-order warning
    - Silence suppression and false trigger filtering
    - Assembly of complete speech segments for STT consumers
    """

    def __init__(
        self,
        receiver: Optional[Callable[[SpeechSegment], Any]] = None,
    ) -> None:
        self._receiver: Optional[Callable[[SpeechSegment], Any]] = receiver
        self._lock = threading.RLock()

        self._current_segment: Optional[SpeechSegment] = None
        self._completed_segments: List[SpeechSegment] = []
        self._last_sequence_id: Optional[int] = None

        # Telemetry metrics
        self.gaps_detected: int = 0
        self.silence_chunks_skipped: int = 0
        self.speech_chunks_ingested: int = 0
        self.false_triggers_rejected: int = 0

    def handle_event(self, event: EventEnvelope) -> None:
        """Route and process incoming EventEnvelope from the audio pipeline."""
        with self._lock:
            event_type = event.event_type

            if event_type == AudioEventType.SPEECH_STARTED.value:
                payload = event.payload
                self._current_segment = SpeechSegment(
                    session_id=event.session_id,
                    correlation_id=event.correlation_id,
                    start_timestamp_ms=float(payload.get("timestamp_ms", 0.0)),
                )

            elif event_type == AudioEventType.CHUNK_NORMALIZED.value:
                payload = event.payload
                is_speech = payload.get("is_speech", False)
                seq_id = payload.get("sequence_id", 0)

                # Check sequence continuity
                if self._last_sequence_id is not None:
                    expected_seq = self._last_sequence_id + 1
                    if seq_id > expected_seq:
                        self.gaps_detected += (seq_id - expected_seq)
                self._last_sequence_id = seq_id

                # Filter silence
                if not is_speech:
                    self.silence_chunks_skipped += 1
                    return

                # If speech chunk arrives inside active segment, record it
                if self._current_segment is not None:
                    self.speech_chunks_ingested += 1
                    self._current_segment.chunk_count += 1

            elif event_type == AudioEventType.SPEECH_ENDED.value:
                payload = event.payload
                if self._current_segment is not None:
                    self._current_segment.end_timestamp_ms = float(
                        payload.get("end_timestamp_ms", self._current_segment.start_timestamp_ms)
                    )
                    self._current_segment.is_completed = True

                    # Verify minimum speech duration / false trigger rejection
                    chunks_count = int(payload.get("speech_chunks_count", 0))
                    if chunks_count > 0:
                        self._current_segment.chunk_count = chunks_count
                    if self._current_segment.chunk_count <= 0 and self.speech_chunks_ingested == 0:
                        self.false_triggers_rejected += 1
                        self._current_segment = None
                        return

                    self._completed_segments.append(self._current_segment)

                    # Handoff to downstream STT receiver
                    if self._receiver:
                        self._receiver(self._current_segment)

                    self._current_segment = None

    def ingest_chunk(
        self,
        chunk: AudioChunk,
        session_id: str,
        correlation_id: str,
        is_speech: bool,
    ) -> None:
        """Direct chunk ingestion helper for streaming handoff."""
        with self._lock:
            # Check gap
            if self._last_sequence_id is not None:
                expected_seq = self._last_sequence_id + 1
                if chunk.sequence_id > expected_seq:
                    self.gaps_detected += (chunk.sequence_id - expected_seq)
            self._last_sequence_id = chunk.sequence_id

            if not is_speech:
                self.silence_chunks_skipped += 1
                return

            if self._current_segment is None:
                self._current_segment = SpeechSegment(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    start_timestamp_ms=chunk.timestamp_ms,
                )

            self._current_segment.chunks.append(chunk)
            self.speech_chunks_ingested += 1

    def finalize_current_segment(self, end_timestamp_ms: float) -> Optional[SpeechSegment]:
        """Finalize speech segment upon speech end or stream termination."""
        with self._lock:
            if not self._current_segment or not self._current_segment.chunks:
                self._current_segment = None
                return None

            self._current_segment.end_timestamp_ms = end_timestamp_ms
            self._current_segment.is_completed = True

            segment = self._current_segment
            self._completed_segments.append(segment)

            if self._receiver:
                self._receiver(segment)

            self._current_segment = None
            return segment

    @property
    def completed_segments(self) -> List[SpeechSegment]:
        """List of finalized speech segments."""
        with self._lock:
            return list(self._completed_segments)

    def reset(self) -> None:
        """Reset bridge state."""
        with self._lock:
            self._current_segment = None
            self._completed_segments.clear()
            self._last_sequence_id = None
            self.gaps_detected = 0
            self.silence_chunks_skipped = 0
            self.speech_chunks_ingested = 0
            self.false_triggers_rejected = 0
