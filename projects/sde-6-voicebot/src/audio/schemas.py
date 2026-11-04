"""Audio Schemas for Academiaai AI Voicebot (SDE 6 - W1).

This module defines the foundational, typed audio data contracts:
- AudioError: Domain-specific exception with error envelopes.
- AudioFormat: Audio configuration with sample-rate and channel validation.
- AudioChunk: Atomic audio segment with monotonic sequence IDs and timestamps.

These contracts are defined once and serve as the single source of truth across
all audio processing, VAD, mock streaming, and speech-to-text integration modules.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Set


class AudioError(Exception):
    """Domain exception raised when audio validation or processing fails.

    Attributes:
        code: Machine-readable error code (e.g. INVALID_SAMPLE_RATE).
        message_safe_for_user: Safe, sanitized error message suitable for display.
        details: Optional dictionary containing debugging context.
    """

    def __init__(
        self,
        code: str,
        message_safe_for_user: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code: str = code
        self.message_safe_for_user: str = message_safe_for_user
        self.details: Dict[str, Any] = details or {}
        super().__init__(f"[{code}] {message_safe_for_user}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error according to the project's error envelope standard."""
        return {
            "code": self.code,
            "message_safe_for_user": self.message_safe_for_user,
            "retryable": False,
            "details_redacted": self.details,
        }


# Permitted standard sample rates in Hertz for audio processing
SUPPORTED_SAMPLE_RATES: Set[int] = {
    8000,   # Telephony narrowband
    11025,  # Low-fidelity
    16000,  # Standard voice / ASR optimal
    22050,  # Mid-fidelity
    24000,  # High-quality voice
    32000,  # Broadcast quality
    44100,  # CD standard
    48000,  # Studio / WebRTC standard
}

# Permitted bit depths (bits per sample)
SUPPORTED_BIT_DEPTHS: Set[int] = {16, 24, 32}


@dataclass(frozen=True)
class AudioFormat:
    """Specification of audio stream encoding and sampling parameters.

    Fields:
        sample_rate_hz: Sample frequency in Hertz (Hz).
                        Constraints: Must be one of {8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000}.
        channels: Number of audio channels.
                  Constraints: Must be 1 (mono) or 2 (stereo).
        bit_depth: Quantization bits per sample (e.g. 16, 24, 32). Defaults to 16.
        encoding: Audio PCM representation format (e.g. 'pcm_s16le'). Defaults to 'pcm_s16le'.
    """

    sample_rate_hz: int = 16000
    channels: int = 1
    bit_depth: int = 16
    encoding: str = "pcm_s16le"

    def __post_init__(self) -> None:
        """Validate sample rate, channel count, and bit depth upon initialization."""
        self.validate()

    def validate(self) -> None:
        """Perform strict invariant checks on audio format parameters.

        Raises:
            AudioError: If sample_rate_hz, channels, or bit_depth violate constraints.
        """
        # Validate sample rate
        if not isinstance(self.sample_rate_hz, int) or self.sample_rate_hz <= 0:
            raise AudioError(
                code="INVALID_SAMPLE_RATE",
                message_safe_for_user=f"Sample rate must be a positive integer, got: {self.sample_rate_hz}",
                details={"sample_rate_hz": self.sample_rate_hz},
            )

        if self.sample_rate_hz not in SUPPORTED_SAMPLE_RATES:
            allowed_rates = sorted(list(SUPPORTED_SAMPLE_RATES))
            raise AudioError(
                code="UNSUPPORTED_SAMPLE_RATE",
                message_safe_for_user=(
                    f"Sample rate {self.sample_rate_hz} Hz is unsupported. "
                    f"Supported rates: {allowed_rates}"
                ),
                details={"sample_rate_hz": self.sample_rate_hz, "supported": allowed_rates},
            )

        # Validate channels
        if not isinstance(self.channels, int) or self.channels not in (1, 2):
            raise AudioError(
                code="INVALID_CHANNEL_COUNT",
                message_safe_for_user=f"Channel count must be 1 (mono) or 2 (stereo), got: {self.channels}",
                details={"channels": self.channels},
            )

        # Validate bit depth
        if self.bit_depth not in SUPPORTED_BIT_DEPTHS:
            raise AudioError(
                code="INVALID_BIT_DEPTH",
                message_safe_for_user=f"Bit depth must be one of {sorted(list(SUPPORTED_BIT_DEPTHS))}, got: {self.bit_depth}",
                details={"bit_depth": self.bit_depth},
            )

    @property
    def bytes_per_sample(self) -> int:
        """Bytes consumed per single channel sample (e.g. 16-bit = 2 bytes)."""
        return self.bit_depth // 8

    @property
    def frame_size_bytes(self) -> int:
        """Total bytes per multi-channel audio frame (channels * bytes_per_sample)."""
        return self.channels * self.bytes_per_sample

    @property
    def bytes_per_second(self) -> int:
        """Total byte throughput per second of audio."""
        return self.sample_rate_hz * self.frame_size_bytes

    def calculate_duration_ms(self, payload_byte_count: int) -> float:
        """Calculate the duration in milliseconds for a given payload size."""
        if self.bytes_per_second == 0:
            return 0.0
        return (payload_byte_count / self.bytes_per_second) * 1000.0

    def calculate_byte_count(self, duration_ms: float) -> int:
        """Calculate the exact byte count required for a given duration in milliseconds."""
        exact_bytes = (duration_ms / 1000.0) * self.bytes_per_second
        frame_aligned = int(round(exact_bytes / self.frame_size_bytes)) * self.frame_size_bytes
        return frame_aligned

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audio format to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioFormat:
        """Deserialize audio format from a dictionary."""
        return cls(
            sample_rate_hz=data.get("sample_rate_hz", 16000),
            channels=data.get("channels", 1),
            bit_depth=data.get("bit_depth", 16),
            encoding=data.get("encoding", "pcm_s16le"),
        )


@dataclass
class AudioChunk:
    """An individual chunk of streamed or captured audio.

    Fields:
        sequence_id: Monotonically increasing sequence index (0, 1, 2, ...).
                     Units: Integer counter.
                     Constraints: Must be >= 0.
        timestamp_ms: Capture or generation timestamp in milliseconds from session start.
                      Units: Milliseconds (ms).
                      Constraints: Must be >= 0.0.
        format: AudioFormat specification governing the payload byte layout.
        payload: Raw PCM audio byte buffer.
                 Constraints: Must be bytes; length must be a multiple of format.frame_size_bytes.
        duration_ms: Audio chunk playback duration in milliseconds.
                     Automatically computed from payload length if not explicitly provided.
    """

    sequence_id: int
    timestamp_ms: float
    format: AudioFormat
    payload: bytes
    duration_ms: float = field(init=False)

    def __post_init__(self) -> None:
        """Compute duration and validate chunk constraints."""
        self.duration_ms = self.format.calculate_duration_ms(len(self.payload))
        self.validate()

    def validate(self, allow_empty: bool = True) -> None:
        """Validate chunk fields against integrity constraints.

        Args:
            allow_empty: If False, raises AudioError when payload is empty.

        Raises:
            AudioError: If sequence_id, timestamp, or payload are invalid or corrupt.
        """
        # Validate sequence ID
        if not isinstance(self.sequence_id, int) or self.sequence_id < 0:
            raise AudioError(
                code="INVALID_SEQUENCE_ID",
                message_safe_for_user=f"Sequence ID must be a non-negative integer, got: {self.sequence_id}",
                details={"sequence_id": self.sequence_id},
            )

        # Validate timestamp
        if not isinstance(self.timestamp_ms, (int, float)) or self.timestamp_ms < 0.0:
            raise AudioError(
                code="INVALID_TIMESTAMP",
                message_safe_for_user=f"Timestamp must be non-negative milliseconds, got: {self.timestamp_ms}",
                details={"timestamp_ms": self.timestamp_ms},
            )

        # Validate payload type
        if not isinstance(self.payload, bytes):
            raise AudioError(
                code="INVALID_PAYLOAD_TYPE",
                message_safe_for_user=f"Audio payload must be of type bytes, got: {type(self.payload).__name__}",
                details={"type": type(self.payload).__name__},
            )

        # Check empty payload constraint
        if not allow_empty and len(self.payload) == 0:
            raise AudioError(
                code="EMPTY_AUDIO_PAYLOAD",
                message_safe_for_user="Audio chunk payload is empty.",
                details={"sequence_id": self.sequence_id},
            )

        # Check frame alignment (detect corrupt or truncated chunks)
        frame_size = self.format.frame_size_bytes
        if len(self.payload) % frame_size != 0:
            misaligned_bytes = len(self.payload) % frame_size
            raise AudioError(
                code="CORRUPT_AUDIO_PAYLOAD",
                message_safe_for_user=(
                    f"Corrupt audio chunk: payload length ({len(self.payload)} bytes) "
                    f"is not a multiple of frame size ({frame_size} bytes, {misaligned_bytes} dangling bytes)."
                ),
                details={
                    "payload_len": len(self.payload),
                    "frame_size": frame_size,
                    "remainder": misaligned_bytes,
                },
            )

    @property
    def is_empty(self) -> bool:
        """Returns True if the payload contains 0 bytes."""
        return len(self.payload) == 0

    @property
    def sample_count(self) -> int:
        """Number of complete audio frames contained in this chunk."""
        return len(self.payload) // self.format.frame_size_bytes

    def to_dict(self, include_payload_base64: bool = False) -> Dict[str, Any]:
        """Serialize chunk to a dictionary metadata representation.

        Args:
            include_payload_base64: If True, encodes payload as base64 string.
                                    If False, includes payload byte length for safety/auditing.
        """
        data: Dict[str, Any] = {
            "sequence_id": self.sequence_id,
            "timestamp_ms": self.timestamp_ms,
            "format": self.format.to_dict(),
            "payload_bytes": len(self.payload),
            "duration_ms": round(self.duration_ms, 2),
            "sample_count": self.sample_count,
        }
        if include_payload_base64:
            data["payload_base64"] = base64.b64encode(self.payload).decode("ascii")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioChunk:
        """Deserialize an AudioChunk from a dictionary."""
        fmt = AudioFormat.from_dict(data["format"])
        if "payload_base64" in data:
            payload = base64.b64decode(data["payload_base64"].encode("ascii"))
        elif "payload" in data:
            payload = data["payload"] if isinstance(data["payload"], bytes) else bytes(data["payload"])
        else:
            payload = b""

        return cls(
            sequence_id=data["sequence_id"],
            timestamp_ms=float(data["timestamp_ms"]),
            format=fmt,
            payload=payload,
        )
