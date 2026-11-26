"""Audio Event Schemas & Event Emitter (SDE 6 - W1 - Days 15–16).

Implements canonical event generation for the audio pipeline:
- Standardized audio event types:
    * audio.speech_started
    * audio.speech_ended
    * audio.chunk_normalized
    * audio.device_lost
    * audio.device_reconnected
    * audio.cancelled
- Wraps every event into the project-standard EventEnvelope with session_id,
  correlation_id, monotonic timestamps, and producer attribution.
- Guaranteed in-order event emission and listener subscription.
"""

from __future__ import annotations

import datetime
from enum import Enum
import threading
from typing import Any, Callable, Dict, List, Optional
import uuid

import sys
import os

# Ensure contracts can be imported cleanly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from contracts.envelope import EventEnvelope
from src.audio.schemas import AudioChunk, AudioError
from src.audio.vad import VADResult


class AudioEventType(str, Enum):
    """Standardized event types emitted by the Audio workstream (W1)."""
    SPEECH_STARTED = "audio.speech_started"
    SPEECH_ENDED = "audio.speech_ended"
    CHUNK_NORMALIZED = "audio.chunk_normalized"
    DEVICE_LOST = "audio.device_lost"
    DEVICE_RECONNECTED = "audio.device_reconnected"
    CAPTURE_CANCELLED = "audio.cancelled"


class AudioEventFactory:
    """Factory creating strictly-typed, schema-compliant EventEnvelope instances."""

    SCHEMA_VERSION: str = "1.0.0"
    PRODUCER_NAME: str = "w1.audio_pipeline"

    @staticmethod
    def ensure_valid_id(given_id: Optional[str]) -> str:
        """Return given_id if non-empty, otherwise generate a fresh UUID v4 string."""
        if given_id and isinstance(given_id, str) and given_id.strip():
            return given_id.strip()
        return str(uuid.uuid4())

    @classmethod
    def create_speech_started(
        cls,
        session_id: str,
        correlation_id: str,
        timestamp_ms: float,
        sequence_id: int,
        energy_rms: float,
        device_id: str,
    ) -> EventEnvelope:
        """Create an audio.speech_started event envelope."""
        session_id = cls.ensure_valid_id(session_id)
        correlation_id = cls.ensure_valid_id(correlation_id)

        payload: Dict[str, Any] = {
            "timestamp_ms": round(timestamp_ms, 3),
            "sequence_id": sequence_id,
            "energy_rms": round(energy_rms, 4),
            "device_id": device_id,
        }
        return EventEnvelope.create(
            event_type=AudioEventType.SPEECH_STARTED.value,
            session_id=session_id,
            correlation_id=correlation_id,
            producer=cls.PRODUCER_NAME,
            payload=payload,
            schema_version=cls.SCHEMA_VERSION,
        )

    @classmethod
    def create_speech_ended(
        cls,
        session_id: str,
        correlation_id: str,
        start_timestamp_ms: float,
        end_timestamp_ms: float,
        total_speech_duration_ms: float,
        speech_chunks_count: int,
    ) -> EventEnvelope:
        """Create an audio.speech_ended event envelope."""
        session_id = cls.ensure_valid_id(session_id)
        correlation_id = cls.ensure_valid_id(correlation_id)

        payload: Dict[str, Any] = {
            "start_timestamp_ms": round(start_timestamp_ms, 3),
            "end_timestamp_ms": round(end_timestamp_ms, 3),
            "total_speech_duration_ms": round(total_speech_duration_ms, 2),
            "speech_chunks_count": speech_chunks_count,
        }
        return EventEnvelope.create(
            event_type=AudioEventType.SPEECH_ENDED.value,
            session_id=session_id,
            correlation_id=correlation_id,
            producer=cls.PRODUCER_NAME,
            payload=payload,
            schema_version=cls.SCHEMA_VERSION,
        )

    @classmethod
    def create_chunk_normalized(
        cls,
        session_id: str,
        correlation_id: str,
        chunk: AudioChunk,
        vad_result: VADResult,
    ) -> EventEnvelope:
        """Create an audio.chunk_normalized event envelope."""
        session_id = cls.ensure_valid_id(session_id)
        correlation_id = cls.ensure_valid_id(correlation_id)

        payload: Dict[str, Any] = {
            "sequence_id": chunk.sequence_id,
            "timestamp_ms": round(chunk.timestamp_ms, 3),
            "duration_ms": round(chunk.duration_ms, 2),
            "payload_bytes": len(chunk.payload),
            "sample_rate_hz": chunk.format.sample_rate_hz,
            "channels": chunk.format.channels,
            "is_speech": vad_result.is_speech,
            "vad_confidence": round(vad_result.confidence, 3),
            "energy_rms": round(vad_result.energy_rms, 4),
            "vad_state": vad_result.state,
        }
        return EventEnvelope.create(
            event_type=AudioEventType.CHUNK_NORMALIZED.value,
            session_id=session_id,
            correlation_id=correlation_id,
            producer=cls.PRODUCER_NAME,
            payload=payload,
            schema_version=cls.SCHEMA_VERSION,
        )

    @classmethod
    def create_device_lost(
        cls,
        session_id: str,
        correlation_id: str,
        device_id: str,
        error_message: str,
        timestamp_ms: float,
    ) -> EventEnvelope:
        """Create an audio.device_lost event envelope."""
        session_id = cls.ensure_valid_id(session_id)
        correlation_id = cls.ensure_valid_id(correlation_id)

        payload: Dict[str, Any] = {
            "device_id": device_id,
            "error_message": error_message,
            "timestamp_ms": round(timestamp_ms, 3),
        }
        return EventEnvelope.create(
            event_type=AudioEventType.DEVICE_LOST.value,
            session_id=session_id,
            correlation_id=correlation_id,
            producer=cls.PRODUCER_NAME,
            payload=payload,
            schema_version=cls.SCHEMA_VERSION,
        )

    @classmethod
    def create_device_reconnected(
        cls,
        session_id: str,
        correlation_id: str,
        device_id: str,
        recovery_duration_ms: float,
        retry_count: int,
    ) -> EventEnvelope:
        """Create an audio.device_reconnected event envelope."""
        session_id = cls.ensure_valid_id(session_id)
        correlation_id = cls.ensure_valid_id(correlation_id)

        payload: Dict[str, Any] = {
            "device_id": device_id,
            "recovery_duration_ms": round(recovery_duration_ms, 2),
            "retry_count": retry_count,
        }
        return EventEnvelope.create(
            event_type=AudioEventType.DEVICE_RECONNECTED.value,
            session_id=session_id,
            correlation_id=correlation_id,
            producer=cls.PRODUCER_NAME,
            payload=payload,
            schema_version=cls.SCHEMA_VERSION,
        )

    @classmethod
    def create_capture_cancelled(
        cls,
        session_id: str,
        correlation_id: str,
        reason: str,
        flushed_chunks_count: int,
    ) -> EventEnvelope:
        """Create an audio.cancelled event envelope."""
        session_id = cls.ensure_valid_id(session_id)
        correlation_id = cls.ensure_valid_id(correlation_id)

        payload: Dict[str, Any] = {
            "reason": reason,
            "flushed_chunks_count": flushed_chunks_count,
        }
        return EventEnvelope.create(
            event_type=AudioEventType.CAPTURE_CANCELLED.value,
            session_id=session_id,
            correlation_id=correlation_id,
            producer=cls.PRODUCER_NAME,
            payload=payload,
            schema_version=cls.SCHEMA_VERSION,
        )


class AudioEventEmitter:
    """Thread-safe event dispatcher maintaining ordered event history and dispatching

    to downstream subscriber callbacks.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._listeners: List[Callable[[EventEnvelope], None]] = []
        self._history: List[EventEnvelope] = []

    def subscribe(self, callback: Callable[[EventEnvelope], None]) -> None:
        """Register a subscriber callback."""
        with self._lock:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[EventEnvelope], None]) -> None:
        """Remove a subscriber callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def emit(self, event: EventEnvelope) -> None:
        """Emit an event to all subscribers and append to in-memory history."""
        with self._lock:
            self._history.append(event)
            for listener in list(self._listeners):
                try:
                    listener(event)
                except Exception:
                    # Individual listener errors should not break the pipeline
                    pass

    def get_history(self) -> List[EventEnvelope]:
        """Return copy of chronologically ordered event history."""
        with self._lock:
            return list(self._history)

    def get_events_by_type(self, event_type: str) -> List[EventEnvelope]:
        """Filter emitted history by event type."""
        with self._lock:
            return [e for e in self._history if e.event_type == event_type]

    def clear(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()

