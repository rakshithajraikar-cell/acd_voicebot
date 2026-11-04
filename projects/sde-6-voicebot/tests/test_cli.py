"""Unit tests for the CLI Demonstration module (SDE 6 - W1 - Days 5–6).

Tests cover:
- CLI streaming execution with default and custom configurations.
- RMS volume meter and ASCII visualization calculations.
- Error handling for invalid parameters.
- Main entry point argument parsing and exit codes.
"""

from unittest.mock import patch
import pytest

from src.audio.schemas import AudioChunk, AudioError, AudioFormat
from src.cli.audio_stream_demo import (
    compute_chunk_rms,
    format_rms_bar,
    main,
    run_stream_demo,
)


class TestCLIAudioStreamDemo:
    """Test suite for audio_stream_demo CLI module."""

    def test_run_stream_demo_default(self, capsys):
        chunks = run_stream_demo(count=5)
        captured = capsys.readouterr()

        assert len(chunks) == 5
        assert "Academiaai AI Voicebot" in captured.out
        assert "STREAM SUMMARY:" in captured.out
        assert "#0" in captured.out
        assert "#4" in captured.out

        for i, chunk in enumerate(chunks):
            assert chunk.sequence_id == i
            assert chunk.timestamp_ms == pytest.approx(i * 20.0)
            assert len(chunk.payload) == 640

    def test_run_stream_demo_stereo_high_rate(self, capsys):
        chunks = run_stream_demo(
            sample_rate_hz=48000,
            channels=2,
            chunk_duration_ms=10.0,
            count=3,
        )
        assert len(chunks) == 3
        # 48000 * 2ch * 2bytes/sample * 10ms = 1920 bytes
        assert len(chunks[0].payload) == 1920
        assert chunks[0].format.channels == 2

    def test_run_stream_demo_invalid_rate_raises_error(self, capsys):
        with pytest.raises(AudioError) as exc_info:
            run_stream_demo(sample_rate_hz=99999)
        assert exc_info.value.code == "UNSUPPORTED_SAMPLE_RATE"

    def test_compute_chunk_rms_and_bar(self):
        fmt = AudioFormat(sample_rate_hz=16000, channels=1, bit_depth=16)

        # Silence (all zeros) -> RMS 0.0
        silence_chunk = AudioChunk(
            sequence_id=0,
            timestamp_ms=0.0,
            format=fmt,
            payload=b"\x00" * 320,
        )
        rms_zero = compute_chunk_rms(silence_chunk)
        assert rms_zero == pytest.approx(0.0)
        assert format_rms_bar(rms_zero, bar_width=5) == "[-----]"

        # Full scale constant signal -> RMS 1.0 approx
        # 32767 packed in 16-bit signed
        import struct
        full_sample = struct.pack("<h", 32767)
        loud_chunk = AudioChunk(
            sequence_id=1,
            timestamp_ms=20.0,
            format=fmt,
            payload=full_sample * 160,
        )
        rms_high = compute_chunk_rms(loud_chunk)
        assert rms_high > 0.95
        assert format_rms_bar(rms_high, bar_width=5) == "[#####]"

    def test_cli_main_success(self):
        with patch("sys.argv", ["audio_stream_demo.py", "--count", "2"]):
            exit_code = main()
            assert exit_code == 0

    def test_cli_main_invalid_rate_exit_code(self):
        with patch("sys.argv", ["audio_stream_demo.py", "--rate", "12345"]):
            exit_code = main()
            assert exit_code == 1
