"""Unit tests for MockMicrophoneSource and DeterministicAudioChunker (SDE 6 - W1 - Days 3–4).

Verifies:
- Bit-for-bit determinism across multiple runs with identical parameters.
- Monotonically increasing sequence IDs.
- Monotonically increasing timestamps aligned with chunk durations.
- Lifecycle controls (reset, stop, total duration bounds).
- Multi-channel support (mono and stereo).
- Deterministic chunking of continuous byte buffers and padding handling.
"""

import pytest

from src.audio.mock_source import DeterministicAudioChunker, MockMicrophoneSource
from src.audio.schemas import AudioError, AudioFormat


class TestDeterministicAudioChunker:
    """Test suite for DeterministicAudioChunker."""

    def test_chunking_exact_length_buffer(self):
        # 16kHz mono 16-bit: 20ms chunk = 640 bytes
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        chunker = DeterministicAudioChunker(audio_format=fmt, chunk_duration_ms=20.0)

        # 5 chunks worth = 3200 bytes (100ms)
        raw_pcm = bytes([i % 256 for i in range(3200)])
        chunks = chunker.chunk_all(raw_pcm)

        assert len(chunks) == 5
        for i, chunk in enumerate(chunks):
            assert chunk.sequence_id == i
            assert chunk.timestamp_ms == pytest.approx(i * 20.0)
            assert chunk.duration_ms == 20.0
            assert len(chunk.payload) == 640

    def test_chunker_determinism_identical_runs(self):
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        chunker1 = DeterministicAudioChunker(audio_format=fmt, chunk_duration_ms=20.0)
        chunker2 = DeterministicAudioChunker(audio_format=fmt, chunk_duration_ms=20.0)

        raw_pcm = b"\x12\x34\x56\x78" * 500  # 2000 bytes

        chunks1 = chunker1.chunk_all(raw_pcm)
        chunks2 = chunker2.chunk_all(raw_pcm)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.sequence_id == c2.sequence_id
            assert c1.timestamp_ms == c2.timestamp_ms
            assert c1.payload == c2.payload
            assert c1.duration_ms == c2.duration_ms

    def test_chunker_padding_final_chunk(self):
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)
        # 640 bytes per chunk. 800 bytes total = 1 full chunk (640) + 160 trailing bytes
        raw_pcm = b"\xaa" * 800

        # With padding: last chunk is padded to 640 bytes with zeros
        chunker_padded = DeterministicAudioChunker(
            audio_format=fmt, chunk_duration_ms=20.0, pad_final_chunk=True
        )
        padded_chunks = chunker_padded.chunk_all(raw_pcm)
        assert len(padded_chunks) == 2
        assert len(padded_chunks[0].payload) == 640
        assert len(padded_chunks[1].payload) == 640
        assert padded_chunks[1].payload[:160] == b"\xaa" * 160
        assert padded_chunks[1].payload[160:] == b"\x00" * 480

        # Without padding: last chunk contains 160 bytes (frame-aligned)
        chunker_unpadded = DeterministicAudioChunker(
            audio_format=fmt, chunk_duration_ms=20.0, pad_final_chunk=False
        )
        unpadded_chunks = chunker_unpadded.chunk_all(raw_pcm)
        assert len(unpadded_chunks) == 2
        assert len(unpadded_chunks[1].payload) == 160

    def test_chunker_empty_input(self):
        chunker = DeterministicAudioChunker()
        chunks = chunker.chunk_all(b"")
        assert chunks == []

    def test_chunker_invalid_input_type(self):
        chunker = DeterministicAudioChunker()
        with pytest.raises(AudioError) as exc_info:
            chunker.chunk_all("string_not_bytes")  # type: ignore
        assert exc_info.value.code == "INVALID_PAYLOAD_TYPE"

    def test_chunker_invalid_duration(self):
        with pytest.raises(AudioError) as exc_info:
            DeterministicAudioChunker(chunk_duration_ms=0)
        assert exc_info.value.code == "INVALID_CHUNK_DURATION"


class TestMockMicrophoneSource:
    """Test suite for MockMicrophoneSource."""

    def test_mock_mic_deterministic_generation(self):
        # Two independent sources with identical parameters must yield bit-for-bit identical chunks
        source1 = MockMicrophoneSource(
            audio_format=AudioFormat(sample_rate_hz=16000, channels=1),
            chunk_duration_ms=20.0,
            frequency_hz=440.0,
            amplitude=0.5,
            total_duration_ms=200.0,
        )
        source2 = MockMicrophoneSource(
            audio_format=AudioFormat(sample_rate_hz=16000, channels=1),
            chunk_duration_ms=20.0,
            frequency_hz=440.0,
            amplitude=0.5,
            total_duration_ms=200.0,
        )

        stream1 = list(source1.stream())
        stream2 = list(source2.stream())

        assert len(stream1) == 10
        assert len(stream2) == 10

        for c1, c2 in zip(stream1, stream2):
            assert c1.sequence_id == c2.sequence_id
            assert c1.timestamp_ms == c2.timestamp_ms
            assert c1.payload == c2.payload
            assert c1.duration_ms == c2.duration_ms

    def test_strictly_monotonic_sequence_and_timestamps(self):
        source = MockMicrophoneSource(
            chunk_duration_ms=20.0,
            total_duration_ms=100.0,
        )
        chunks = list(source.stream())

        assert len(chunks) == 5

        for i, chunk in enumerate(chunks):
            assert chunk.sequence_id == i
            expected_ts = i * 20.0
            assert chunk.timestamp_ms == pytest.approx(expected_ts)

    def test_source_lifecycle_stop(self):
        source = MockMicrophoneSource(chunk_duration_ms=20.0)
        c0 = source.read_chunk()
        assert c0 is not None
        assert c0.sequence_id == 0

        source.stop()
        c1 = source.read_chunk()
        assert c1 is None

    def test_source_lifecycle_reset(self):
        source = MockMicrophoneSource(chunk_duration_ms=20.0, total_duration_ms=40.0)
        first_run = list(source.stream())
        assert len(first_run) == 2
        assert source.read_chunk() is None

        source.reset()
        assert source.current_sequence_id == 0
        assert source.current_timestamp_ms == 0.0

        second_run = list(source.stream())
        assert len(second_run) == 2
        assert second_run[0].payload == first_run[0].payload
        assert second_run[1].payload == first_run[1].payload

    def test_stereo_mock_mic_payload_alignment(self):
        stereo_fmt = AudioFormat(sample_rate_hz=48000, channels=2, bit_depth=16)
        source = MockMicrophoneSource(
            audio_format=stereo_fmt,
            chunk_duration_ms=10.0,
            total_duration_ms=30.0,
        )
        chunks = list(source.stream())
        assert len(chunks) == 3

        for chunk in chunks:
            # 48000Hz * 10ms = 480 samples. 2 channels * 2 bytes = 4 bytes/sample. 480 * 4 = 1920 bytes.
            assert len(chunk.payload) == 1920
            assert chunk.format.channels == 2
            assert chunk.sample_count == 480
