"""Bounded Stream Buffer with Backpressure & Telemetry Counters (SDE 6 - W1 - Days 12–13).

Provides:
- BackpressurePolicy: DROP_OLDEST, DROP_NEWEST, or REJECT.
- BufferStats: Detailed telemetry on queue depth, dropped chunks, gaps, and late frames.
- BoundedAudioBuffer: Thread-safe, bounded FIFO buffer with backpressure enforcement,
  gap detection, out-of-order/late chunk tracking, and clean release lifecycle.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import threading
from typing import Deque, List, Optional

from src.audio.schemas import AudioChunk, AudioError


class BackpressurePolicy(str, Enum):
    """Policy applied when the buffer reaches its maximum capacity."""
    DROP_OLDEST = "drop_oldest"  # Discard oldest chunk to prioritize live, fresh audio
    DROP_NEWEST = "drop_newest"  # Discard incoming chunk if buffer is saturated
    REJECT = "reject"            # Raise AudioError if capacity exceeded


@dataclass(frozen=True)
class BufferStats:
    """Telemetry metrics snapshot for the BoundedAudioBuffer."""
    current_size: int
    capacity: int
    total_received: int
    total_emitted: int
    total_dropped: int
    gaps_detected: int
    late_chunks_detected: int
    queued_duration_ms: float


class BoundedAudioBuffer:
    """Thread-safe bounded audio buffer with backpressure and anomaly telemetry.

    Parameters:
        capacity: Maximum number of AudioChunks allowed in the queue.
        policy: Backpressure policy (default: DROP_OLDEST).
    """

    def __init__(
        self,
        capacity: int = 50,
        policy: BackpressurePolicy = BackpressurePolicy.DROP_OLDEST,
    ) -> None:
        if capacity <= 0:
            raise AudioError(
                code="INVALID_BUFFER_CAPACITY",
                message_safe_for_user=f"Buffer capacity must be positive, got: {capacity}",
            )

        self.capacity: int = capacity
        self.policy: BackpressurePolicy = policy

        self._queue: Deque[AudioChunk] = deque()
        self._lock = threading.RLock()
        self._not_empty_cond = threading.Condition(self._lock)

        # Telemetry counters
        self._total_received: int = 0
        self._total_emitted: int = 0
        self._total_dropped: int = 0
        self._gaps_detected: int = 0
        self._late_chunks_detected: int = 0
        self._last_sequence_id: Optional[int] = None
        self._is_closed: bool = False

    @property
    def is_empty(self) -> bool:
        """Check if buffer currently holds 0 chunks."""
        with self._lock:
            return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Check if buffer is at full capacity."""
        with self._lock:
            return len(self._queue) >= self.capacity

    @property
    def queued_duration_ms(self) -> float:
        """Total duration of audio currently waiting in queue."""
        with self._lock:
            return sum(c.duration_ms for c in self._queue)

    def push(self, chunk: AudioChunk) -> bool:
        """Push an AudioChunk into the bounded buffer applying backpressure.

        Tracks sequence gaps and late arrivals.

        Returns:
            True if chunk was enqueued, False if dropped due to backpressure.
        """
        with self._lock:
            if self._is_closed:
                raise AudioError(
                    code="BUFFER_CLOSED",
                    message_safe_for_user="Cannot push chunk into a closed or released buffer.",
                )

            self._total_received += 1

            # Anomaly Tracking: Sequence Ordering, Gaps & Late Chunks
            if self._last_sequence_id is not None:
                expected_seq = self._last_sequence_id + 1
                if chunk.sequence_id < expected_seq:
                    self._late_chunks_detected += 1
                elif chunk.sequence_id > expected_seq:
                    self._gaps_detected += (chunk.sequence_id - expected_seq)

            self._last_sequence_id = chunk.sequence_id

            # Capacity & Backpressure enforcement
            if len(self._queue) >= self.capacity:
                if self.policy == BackpressurePolicy.DROP_OLDEST:
                    dropped = self._queue.popleft()
                    self._total_dropped += 1
                    self._queue.append(chunk)
                    self._not_empty_cond.notify()
                    return True
                elif self.policy == BackpressurePolicy.DROP_NEWEST:
                    self._total_dropped += 1
                    return False
                elif self.policy == BackpressurePolicy.REJECT:
                    raise AudioError(
                        code="BUFFER_OVERFLOW",
                        message_safe_for_user=(
                            f"Buffer overflow: capacity of {self.capacity} chunks exceeded."
                        ),
                        details={"capacity": self.capacity, "received": self._total_received},
                    )

            # Normal enqueue
            self._queue.append(chunk)
            self._not_empty_cond.notify()
            return True

    def pop(self, timeout_s: Optional[float] = None) -> Optional[AudioChunk]:
        """Pop the next AudioChunk from the queue (FIFO order)."""
        with self._lock:
            if len(self._queue) == 0:
                if timeout_s is None or timeout_s <= 0:
                    return None
                # Wait for data or timeout
                self._not_empty_cond.wait(timeout=timeout_s)
                if len(self._queue) == 0:
                    return None

            chunk = self._queue.popleft()
            self._total_emitted += 1
            return chunk

    def pop_all(self) -> List[AudioChunk]:
        """Drain all currently queued chunks."""
        with self._lock:
            chunks = list(self._queue)
            self._total_emitted += len(chunks)
            self._queue.clear()
            return chunks

    def release(self) -> List[AudioChunk]:
        """Release and close the buffer upon stop, returning any remaining chunks."""
        with self._lock:
            self._is_closed = True
            remaining = list(self._queue)
            self._queue.clear()
            self._not_empty_cond.notify_all()
            return remaining

    def reset(self) -> None:
        """Reset the buffer state and telemetry counters for reuse."""
        with self._lock:
            self._queue.clear()
            self._total_received = 0
            self._total_emitted = 0
            self._total_dropped = 0
            self._gaps_detected = 0
            self._late_chunks_detected = 0
            self._last_sequence_id = None
            self._is_closed = False

    def get_stats(self) -> BufferStats:
        """Get an instantaneous snapshot of buffer metrics and health counters."""
        with self._lock:
            return BufferStats(
                current_size=len(self._queue),
                capacity=self.capacity,
                total_received=self._total_received,
                total_emitted=self._total_emitted,
                total_dropped=self._total_dropped,
                gaps_detected=self._gaps_detected,
                late_chunks_detected=self._late_chunks_detected,
                queued_duration_ms=round(self.queued_duration_ms, 2),
            )
