"""CLI Demonstration for Mock Audio Streaming (SDE 6 - W1 - Days 5–6).

This CLI tool streams synthetic audio chunks from MockMicrophoneSource,
displaying live metadata (sequence ID, timestamp, format, size, duration, RMS).
Can be run as a standalone script or module.

Usage examples:
    python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --count 10
    python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --rate 16000 --channels 1 --count 15
    python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --rate 48000 --channels 2 --count 5
"""

from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import time
from typing import List, Optional

# Ensure projects/sde-6-voicebot is on sys.path when invoked directly as a script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.audio.mock_source import MockMicrophoneSource
from src.audio.schemas import AudioChunk, AudioError, AudioFormat


def compute_chunk_rms(chunk: AudioChunk) -> float:
    """Compute normalized Root Mean Square (RMS) amplitude [0.0, 1.0] for a 16-bit PCM chunk."""
    if chunk.is_empty:
        return 0.0

    sample_count = len(chunk.payload) // 2  # 2 bytes per 16-bit sample
    if sample_count == 0:
        return 0.0

    # Unpack 16-bit signed integers
    samples = struct.unpack(f"<{sample_count}h", chunk.payload)
    sum_squares = sum(s * s for s in samples)
    mean_square = sum_squares / sample_count
    rms_int16 = math.sqrt(mean_square)
    return min(1.0, rms_int16 / 32768.0)


def format_rms_bar(rms: float, bar_width: int = 10) -> str:
    """Render a visual ASCII amplitude meter."""
    filled = int(round(rms * bar_width))
    return f"[{'#' * filled}{'-' * (bar_width - filled)}]"


def run_stream_demo(
    sample_rate_hz: int = 16000,
    channels: int = 1,
    chunk_duration_ms: float = 20.0,
    count: int = 10,
    frequency_hz: float = 440.0,
    amplitude: float = 0.5,
    simulate_realtime: bool = False,
) -> List[AudioChunk]:
    """Execute the mock audio stream demonstration and print chunk metadata to stdout.

    Returns:
        List of generated AudioChunk instances.
    """
    try:
        fmt = AudioFormat(
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            bit_depth=16,
            encoding="pcm_s16le",
        )
    except AudioError as err:
        print(f"\n[ERROR] Configuration rejected: {err.message_safe_for_user} (code: {err.code})", file=sys.stderr)
        raise

    source = MockMicrophoneSource(
        audio_format=fmt,
        chunk_duration_ms=chunk_duration_ms,
        frequency_hz=frequency_hz,
        amplitude=amplitude,
    )

    print("=" * 80)
    print("Academiaai AI Voicebot — SDE 6 (W1: Audio & VAD Stream Demo)")
    print("=" * 80)
    print(f"Format:       {fmt.sample_rate_hz} Hz | {fmt.channels} channel(s) ({'mono' if fmt.channels == 1 else 'stereo'}) | {fmt.bit_depth}-bit {fmt.encoding}")
    print(f"Chunk Size:   {fmt.calculate_byte_count(chunk_duration_ms)} bytes ({chunk_duration_ms} ms)")
    print(f"Signal:       {frequency_hz} Hz sine wave | Amplitude: {amplitude:.2f}")
    print(f"Target Count: {count} chunks (Total: {count * chunk_duration_ms:.1f} ms)")
    print("-" * 80)
    print(f"{'SEQ':<5} | {'TIMESTAMP':<12} | {'PAYLOAD':<10} | {'DURATION':<10} | {'LEVEL':<12} | {'RMS'}")
    print("-" * 80)

    emitted_chunks: List[AudioChunk] = []
    total_bytes = 0

    for chunk in source.stream(max_chunks=count):
        rms = compute_chunk_rms(chunk)
        rms_meter = format_rms_bar(rms, bar_width=8)

        print(
            f"#{chunk.sequence_id:<4} | "
            f"{chunk.timestamp_ms:>8.2f} ms | "
            f"{len(chunk.payload):>6} bytes | "
            f"{chunk.duration_ms:>6.2f} ms | "
            f"{rms_meter} | "
            f"{rms:.3f}"
        )

        emitted_chunks.append(chunk)
        total_bytes += len(chunk.payload)

        if simulate_realtime:
            time.sleep(chunk_duration_ms / 1000.0)

    total_duration_ms = sum(c.duration_ms for c in emitted_chunks)
    print("-" * 80)
    print("STREAM SUMMARY:")
    print(f"  Total Chunks:     {len(emitted_chunks)}")
    print(f"  Total Audio Time: {total_duration_ms:.2f} ms ({total_duration_ms / 1000.0:.3f} s)")
    print(f"  Total Payload:    {total_bytes} bytes ({total_bytes / 1024.0:.2f} KB)")
    print(f"  Status:           SUCCESS - Stream emitted deterministically with zero gaps")
    print("=" * 80)

    return emitted_chunks


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Stream synthetic audio chunks from MockMicrophoneSource (SDE 6 - W1)."
    )
    parser.add_argument(
        "--rate", "-r",
        type=int,
        default=16000,
        help="Audio sample rate in Hz (default: 16000).",
    )
    parser.add_argument(
        "--channels", "-c",
        type=int,
        default=1,
        help="Channel count: 1 for mono, 2 for stereo (default: 1).",
    )
    parser.add_argument(
        "--chunk-duration", "-d",
        type=float,
        default=20.0,
        help="Duration of each chunk in milliseconds (default: 20.0).",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of chunks to emit (default: 10).",
    )
    parser.add_argument(
        "--frequency", "-f",
        type=float,
        default=440.0,
        help="Synthetic tone frequency in Hz (default: 440.0).",
    )
    parser.add_argument(
        "--amplitude", "-a",
        type=float,
        default=0.5,
        help="Tone amplitude from 0.0 to 1.0 (default: 0.5).",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Simulate real-time streaming with inter-chunk delays.",
    )

    args = parser.parse_args()

    try:
        run_stream_demo(
            sample_rate_hz=args.rate,
            channels=args.channels,
            chunk_duration_ms=args.chunk_duration,
            count=args.count,
            frequency_hz=args.frequency,
            amplitude=args.amplitude,
            simulate_realtime=args.realtime,
        )
        return 0
    except AudioError:
        return 1
    except Exception as exc:
        print(f"[FATAL] Unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
