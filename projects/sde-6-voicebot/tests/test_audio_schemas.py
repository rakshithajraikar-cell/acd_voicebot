"""Unit tests for Audio Schemas (SDE 6 - W1 - Days 1–2).

Tests cover:
- AudioFormat validation (sample rate, channel count, bit depth, calculations)
- AudioChunk validation (sequence IDs, timestamps, corrupt/misaligned payloads, empty payloads)
- Serialization and deserialization roundtrips
- Error envelope structure and formatting
"""

import pytest

from src.audio.schemas import (
    AudioChunk,
    AudioError,
    AudioFormat,
    SUPPORTED_SAMPLE_RATES,
)


class TestAudioFormat:
    """Test suite for AudioFormat specification and validation."""

    def test_default_audio_format(self):
        fmt = AudioFormat()
        assert fmt.sample_rate_hz == 16000
        assert fmt.channels == 1
        assert fmt.bit_depth == 16
        assert fmt.encoding == "pcm_s16le"
        assert fmt.bytes_per_sample == 2
        assert fmt.frame_size_bytes == 2
        assert fmt.bytes_per_second == 32000

    def test_supported_sample_rates(self):
        for rate in SUPPORTED_SAMPLE_RATES:
            fmt = AudioFormat(sample_rate_hz=rate, channels=1)
            assert fmt.sample_rate_hz == rate

    def test_stereo_format(self):
        fmt = AudioFormat(sample_rate_hz=48000, channels=2, bit_depth=16)
        assert fmt.channels == 2
        assert fmt.frame_size_bytes == 4
        assert fmt.bytes_per_second == 192000

    def test_invalid_negative_or_zero_sample_rate(self):
        for invalid_rate in [0, -16000, "16000"]:
            with pytest.raises(AudioError) as exc_info:
                AudioFormat(sample_rate_hz=invalid_rate)  # type: ignore
            assert exc_info.value.code == "INVALID_SAMPLE_RATE"
            assert "positive integer" in exc_info.value.message_safe_for_user

    def test_unsupported_sample_rate(self):
        with pytest.raises(AudioError) as exc_info:
            AudioFormat(sample_rate_hz=12345)
        assert exc_info.value.code == "UNSUPPORTED_SAMPLE_RATE"
        assert "unsupported" in exc_info.value.message_safe_for_user.lower()

    def test_invalid_channel_count(self):
        for invalid_channel in [0, 3, 5, -1, "mono"]:
            with pytest.raises(AudioError) as exc_info:
                AudioFormat(channels=invalid_channel)  # type: ignore
            assert exc_info.value.code == "INVALID_CHANNEL_COUNT"
            assert "1 (mono) or 2 (stereo)" in exc_info.value.message_safe_for_user

    def test_invalid_bit_depth(self):
        for invalid_depth in [8, 12, 64]:
            with pytest.raises(AudioError) as exc_info:
                AudioFormat(bit_depth=invalid_depth)
            assert exc_info.value.code == "INVALID_BIT_DEPTH"

    def test_duration_and_byte_calculations(self):
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        # 16000 samples/sec * 2 bytes/sample = 32000 bytes/sec
        # 6400 bytes = 200 ms
        duration = fmt.calculate_duration_ms(6400)
        assert duration == 200.0

        calculated_bytes = fmt.calculate_byte_count(200.0)
        assert calculated_bytes == 6400

    def test_serialization_roundtrip(self):
        fmt = AudioFormat(sample_rate_hz=44100, channels=2, bit_depth=16)
        data = fmt.to_dict()
        assert data["sample_rate_hz"] == 44100
        assert data["channels"] == 2

        restored = AudioFormat.from_dict(data)
        assert restored == fmt


class TestAudioChunk:
    """Test suite for AudioChunk creation, invariants, and validation."""

    def test_valid_audio_chunk(self):
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        # 320 bytes = 160 samples = 10 ms
        payload = b"\x00" * 320
        chunk = AudioChunk(
            sequence_id=0,
            timestamp_ms=0.0,
            format=fmt,
            payload=payload,
        )

        assert chunk.sequence_id == 0
        assert chunk.timestamp_ms == 0.0
        assert chunk.duration_ms == 10.0
        assert chunk.sample_count == 160
        assert not chunk.is_empty

    def test_invalid_negative_sequence_id(self):
        fmt = AudioFormat()
        with pytest.raises(AudioError) as exc_info:
            AudioChunk(
                sequence_id=-1,
                timestamp_ms=0.0,
                format=fmt,
                payload=b"\x00\x00",
            )
        assert exc_info.value.code == "INVALID_SEQUENCE_ID"

    def test_invalid_negative_timestamp(self):
        fmt = AudioFormat()
        with pytest.raises(AudioError) as exc_info:
            AudioChunk(
                sequence_id=0,
                timestamp_ms=-50.0,
                format=fmt,
                payload=b"\x00\x00",
            )
        assert exc_info.value.code == "INVALID_TIMESTAMP"

    def test_invalid_payload_type(self):
        fmt = AudioFormat()
        with pytest.raises(AudioError) as exc_info:
            AudioChunk(
                sequence_id=0,
                timestamp_ms=0.0,
                format=fmt,
                payload="not_bytes",  # type: ignore
            )
        assert exc_info.value.code == "INVALID_PAYLOAD_TYPE"

    def test_corrupt_payload_misaligned_bytes(self):
        # 16-bit stereo frame = 2 channels * 2 bytes = 4 bytes per frame
        fmt = AudioFormat(sample_rate_hz=16000, channels=2, bit_depth=16)
        # 5 bytes is not divisible by 4 (corrupted / truncated)
        with pytest.raises(AudioError) as exc_info:
            AudioChunk(
                sequence_id=1,
                timestamp_ms=20.0,
                format=fmt,
                payload=b"\x00\x01\x02\x03\x04",
            )
        assert exc_info.value.code == "CORRUPT_AUDIO_PAYLOAD"
        assert "not a multiple of frame size" in exc_info.value.message_safe_for_user

    def test_empty_payload_validation(self):
        fmt = AudioFormat()
        empty_chunk = AudioChunk(
            sequence_id=0,
            timestamp_ms=0.0,
            format=fmt,
            payload=b"",
        )
        assert empty_chunk.is_empty
        assert empty_chunk.duration_ms == 0.0

        with pytest.raises(AudioError) as exc_info:
            empty_chunk.validate(allow_empty=False)
        assert exc_info.value.code == "EMPTY_AUDIO_PAYLOAD"

    def test_serialization_and_deserialization(self):
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        payload = b"\x01\x02\x03\x04"
        chunk = AudioChunk(
            sequence_id=5,
            timestamp_ms=100.0,
            format=fmt,
            payload=payload,
        )

        # Dict without base64 payload (for logging/auditing)
        summary = chunk.to_dict(include_payload_base64=False)
        assert summary["sequence_id"] == 5
        assert summary["payload_bytes"] == 4
        assert "payload_base64" not in summary

        # Dict with base64 payload for wire transfer
        wire_data = chunk.to_dict(include_payload_base64=True)
        assert "payload_base64" in wire_data

        restored = AudioChunk.from_dict(wire_data)
        assert restored.sequence_id == chunk.sequence_id
        assert restored.timestamp_ms == chunk.timestamp_ms
        assert restored.payload == chunk.payload
        assert restored.duration_ms == chunk.duration_ms


class TestAudioError:
    """Test suite for AudioError exception envelopes."""

    def test_audio_error_envelope(self):
        err = AudioError(
            code="DEVICE_UNAVAILABLE",
            message_safe_for_user="The requested audio input device is unavailable.",
            details={"device_id": "mic-default"},
        )
        assert str(err) == "[DEVICE_UNAVAILABLE] The requested audio input device is unavailable."
        envelope = err.to_dict()
        assert envelope["code"] == "DEVICE_UNAVAILABLE"
        assert envelope["retryable"] is False
        assert envelope["details_redacted"]["device_id"] == "mic-default"
