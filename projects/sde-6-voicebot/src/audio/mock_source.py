"""Mock Audio Source and Deterministic Chunker (SDE 6 - W1 - Days 3–4).

This module provides:
1. DeterministicAudioChunker: Slices raw PCM streams into consistent AudioChunk
   sequences with monotonic IDs and millisecond timestamps.
2. MockMicrophoneSource: A synthetic, deterministic microphone emitter for local
   development, testing, and CI without requiring physical microphone access.
"""

from __future__ import annotations

import math
import struct
from typing import Iterator, List, Optional

from src.audio.schemas import AudioChunk, AudioError, AudioFormat


class DeterministicAudioChunker:
    """Slices raw audio bytes into discrete, deterministic AudioChunks.

    Given identical input bytes and parameters, this chunker guarantees
    identical chunk outputs (payload, sequence_id, timestamp_ms).

    Attributes:
        format: The AudioFormat defining frame size and sample rate.
        chunk_duration_ms: Duration of each chunk in milliseconds (default: 20ms).
        pad_final_chunk: Whether to pad an incomplete final chunk with silence.
    """

    def __init__(
        self,
        audio_format: Optional[AudioFormat] = None,
        chunk_duration_ms: float = 20.0,
        pad_final_chunk: bool = False,
    ) -> None:
        self.format: AudioFormat = audio_format or AudioFormat()
        if chunk_duration_ms <= 0:
            raise AudioError(
                code="INVALID_CHUNK_DURATION",
                message_safe_for_user=f"Chunk duration must be positive, got: {chunk_duration_ms}",
                details={"chunk_duration_ms": chunk_duration_ms},
            )
        self.chunk_duration_ms: float = chunk_duration_ms
        self.chunk_size_bytes: int = self.format.calculate_byte_count(chunk_duration_ms)
        self.pad_final_chunk: bool = pad_final_chunk

    def chunk_bytes(
        self,
        raw_bytes: bytes,
        start_sequence_id: int = 0,
        start_timestamp_ms: float = 0.0,
    ) -> Iterator[AudioChunk]:
        """Slice raw audio bytes into an iterator of AudioChunk objects.

        Args:
            raw_bytes: Raw PCM audio byte sequence.
            start_sequence_id: Initial sequence ID (default: 0).
            start_timestamp_ms: Initial timestamp in milliseconds (default: 0.0).

        Yields:
            AudioChunk instances with monotonically increasing sequence IDs.
        """
        if not isinstance(raw_bytes, bytes):
            raise AudioError(
                code="INVALID_PAYLOAD_TYPE",
                message_safe_for_user="Input data to chunker must be of type bytes.",
                details={"received_type": type(raw_bytes).__name__},
            )

        if len(raw_bytes) == 0:
            return

        total_bytes = len(raw_bytes)
        current_offset = 0
        current_seq = start_sequence_id
        current_timestamp = start_timestamp_ms

        while current_offset < total_bytes:
            end_offset = min(current_offset + self.chunk_size_bytes, total_bytes)
            slice_bytes = raw_bytes[current_offset:end_offset]

            # Check if this is a partial chunk at the end
            if len(slice_bytes) < self.chunk_size_bytes:
                if self.pad_final_chunk:
                    # Pad remainder with silence (zeros)
                    padding_needed = self.chunk_size_bytes - len(slice_bytes)
                    slice_bytes = slice_bytes + (b"\x00" * padding_needed)
                else:
                    # Ensure partial chunk is still aligned to frame boundary
                    frame_rem = len(slice_bytes) % self.format.frame_size_bytes
                    if frame_rem != 0:
                        slice_bytes = slice_bytes[:-frame_rem]
                    if len(slice_bytes) == 0:
                        break

            chunk = AudioChunk(
                sequence_id=current_seq,
                timestamp_ms=round(current_timestamp, 3),
                format=self.format,
                payload=slice_bytes,
            )

            yield chunk

            current_offset += len(slice_bytes)
            current_seq += 1
            current_timestamp += chunk.duration_ms

    def chunk_all(
        self,
        raw_bytes: bytes,
        start_sequence_id: int = 0,
        start_timestamp_ms: float = 0.0,
    ) -> List[AudioChunk]:
        """Convenience method returning all chunks as a materialized list."""
        return list(
            self.chunk_bytes(
                raw_bytes=raw_bytes,
                start_sequence_id=start_sequence_id,
                start_timestamp_ms=start_timestamp_ms,
            )
        )


class MockMicrophoneSource:
    """Deterministic mock microphone that emits synthesized audio chunks.

    Generates reproducible PCM audio waveforms (e.g. harmonic sine wave tone)
    without relying on external sound hardware or audio drivers.

    Guarantees:
    - Same seed & parameters -> identical byte stream and chunks across runs.
    - Strictly monotonic sequence IDs (0, 1, 2, ...).
    - Accurate, monotonic timestamps matching sample duration.
    """

    def __init__(
        self,
        audio_format: Optional[AudioFormat] = None,
        chunk_duration_ms: float = 20.0,
        frequency_hz: float = 440.0,
        amplitude: float = 0.5,
        total_duration_ms: Optional[float] = None,
    ) -> None:
        """Initialize the mock microphone source.

        Args:
            audio_format: Audio format parameters (default: 16kHz mono 16-bit).
            chunk_duration_ms: Duration of each generated chunk in ms (default: 20ms).
            frequency_hz: Frequency of the synthetic audio tone in Hz (default: 440Hz / A4).
            amplitude: Signal amplitude between 0.0 (silence) and 1.0 (full scale).
            total_duration_ms: Total duration to generate. If None, acts as infinite stream.
        """
        self.format: AudioFormat = audio_format or AudioFormat()
        self.chunk_duration_ms: float = chunk_duration_ms
        self.frequency_hz: float = frequency_hz
        self.amplitude: float = max(0.0, min(1.0, amplitude))
        self.total_duration_ms: Optional[float] = total_duration_ms

        self._samples_per_chunk: int = int(
            round(self.chunk_duration_ms / 1000.0 * self.format.sample_rate_hz)
        )
        self._current_sequence_id: int = 0
        self._current_timestamp_ms: float = 0.0
        self._sample_index: int = 0
        self._is_active: bool = True

    @property
    def current_sequence_id(self) -> int:
        """The sequence ID that will be assigned to the next chunk."""
        return self._current_sequence_id

    @property
    def current_timestamp_ms(self) -> float:
        """The timestamp that will be assigned to the next chunk."""
        return round(self._current_timestamp_ms, 3)

    def reset(self) -> None:
        """Reset the source state to beginning (sequence_id 0, timestamp 0.0)."""
        self._current_sequence_id = 0
        self._current_timestamp_ms = 0.0
        self._sample_index = 0
        self._is_active = True

    def stop(self) -> None:
        """Stop emitting chunks from this mock microphone."""
        self._is_active = False

    def _generate_pcm16_chunk_payload(self, sample_count: int) -> bytes:
        """Synthesize deterministic 16-bit PCM samples using a sine tone.

        Produces multi-channel interleaved bytes if channels == 2.
        """
        max_int16 = 32767.0
        scale = self.amplitude * max_int16
        two_pi_f = 2.0 * math.pi * self.frequency_hz
        sr = float(self.format.sample_rate_hz)
        channels = self.format.channels

        sample_bytes_list: List[bytes] = []

        for i in range(sample_count):
            t = (self._sample_index + i) / sr
            sample_val = int(round(math.sin(two_pi_f * t) * scale))
            # Clamp to 16-bit signed range
            sample_val = max(-32768, min(32767, sample_val))
            packed_sample = struct.pack("<h", sample_val)

            # Duplicate across channels for mono/stereo
            sample_bytes_list.append(packed_sample * channels)

        self._sample_index += sample_count
        return b"".join(sample_bytes_list)

    def read_chunk(self) -> Optional[AudioChunk]:
        """Generate and return the next AudioChunk, or None if stopped or duration reached."""
        if not self._is_active:
            return None

        if self.total_duration_ms is not None:
            if self._current_timestamp_ms >= self.total_duration_ms:
                return None

        # Determine sample count for this chunk
        remaining_ms: Optional[float] = None
        if self.total_duration_ms is not None:
            remaining_ms = self.total_duration_ms - self._current_timestamp_ms

        if remaining_ms is not None and remaining_ms < self.chunk_duration_ms:
            samples_to_gen = max(
                1, int(round(remaining_ms / 1000.0 * self.format.sample_rate_hz))
            )
        else:
            samples_to_gen = self._samples_per_chunk

        payload = self._generate_pcm16_chunk_payload(samples_to_gen)

        chunk = AudioChunk(
            sequence_id=self._current_sequence_id,
            timestamp_ms=round(self._current_timestamp_ms, 3),
            format=self.format,
            payload=payload,
        )

        self._current_sequence_id += 1
        self._current_timestamp_ms += chunk.duration_ms

        return chunk

    def stream(self, max_chunks: Optional[int] = None) -> Iterator[AudioChunk]:
        """Stream chunks from the mock microphone.

        Args:
            max_chunks: Optional limit on the number of chunks to yield.
        """
        emitted = 0
        while True:
            if max_chunks is not None and emitted >= max_chunks:
                break
            chunk = self.read_chunk()
            if chunk is None:
                break
            yield chunk
            emitted += 1
