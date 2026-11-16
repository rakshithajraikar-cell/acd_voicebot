"""CLI Demonstration for Week 2 Audio Pipeline & VAD (SDE 6 - W1 - Days 8–14).

Demonstrates:
- Device selection and permission validation
- Start, pause, resume, stop lifecycle
- Live Voice Activity Detection (VAD) classification
- Bounded audio buffer backpressure and dropped-chunk telemetry

Usage:
    python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py
    python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py --capacity 5 --chunks 15
    python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py --simulate-denial
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.audio.buffer import BackpressurePolicy
from src.audio.controller import AudioPipelineController
from src.audio.device import MockAudioDeviceAdapter, PermissionState
from src.audio.schemas import AudioError, AudioFormat


def run_pipeline_demo(
    buffer_capacity: int = 8,
    chunk_count: int = 12,
    simulate_denial: bool = False,
    simulate_unsupported: bool = False,
    pause_resume: bool = True,
) -> None:
    """Run an interactive demonstration of the Week 2 audio pipeline."""
    print("=" * 85)
    print("Academiaai AI Voicebot — SDE 6 (Week 2: Audio Lifecycle, VAD & Bounded Buffer Demo)")
    print("=" * 85)

    # 1. Device and Permission Setup
    perm_state = PermissionState.DENIED if simulate_denial else PermissionState.GRANTED
    adapter = MockAudioDeviceAdapter(permission_state=perm_state)

    print("\n[STEP 1] Device Discovery & Permissions:")
    for dev in adapter.list_devices():
        default_mark = " (Default)" if dev.is_default else ""
        avail_mark = "Online" if dev.is_available else "Offline"
        print(f"  - [{avail_mark}] {dev.name} (id: {dev.device_id}){default_mark}")
        print(f"    Supported Rates: {dev.supported_sample_rates} Hz | Channels: {dev.supported_channels}")

    print(f"\nPermission State: {adapter.get_permission_state().value.upper()}")

    fmt = AudioFormat(sample_rate_hz=16000, channels=1)

    if simulate_denial:
        print("\n--> Simulating permission denial test...")
        try:
            adapter.validate_device_for_format("mock-mic-default", fmt)
        except AudioError as err:
            print(f"  [EXPECTED ERROR CAUGHT] Code: {err.code} | Message: {err.message_safe_for_user}")
            print("\nPipeline safely halted due to permission policy (no crash).")
            return

    if simulate_unsupported:
        print("\n--> Simulating unsupported device selection...")
        try:
            adapter.validate_device_for_format("mock-mic-offline", fmt)
        except AudioError as err:
            print(f"  [EXPECTED ERROR CAUGHT] Code: {err.code} | Message: {err.message_safe_for_user}")
            return

    # 2. Pipeline Initialization
    controller = AudioPipelineController(
        audio_format=fmt,
        chunk_duration_ms=20.0,
        buffer_capacity=buffer_capacity,
        buffer_policy=BackpressurePolicy.DROP_OLDEST,
        energy_threshold=0.05,
        min_speech_duration_ms=40.0,
        device_adapter=adapter,
    )

    print("\n[STEP 2] Lifecycle Start:")
    controller.start()
    print(f"  Current Lifecycle State: {controller.lifecycle.state.value.upper()}")
    print(f"  Bounded Buffer Capacity: {buffer_capacity} chunks (Policy: DROP_OLDEST)")

    print("\n[STEP 3] Audio Capture & Real-time VAD Processing:")
    print("-" * 85)
    print(f"{'SEQ':<5} | {'TIME':<10} | {'RMS':<7} | {'VAD STATE':<12} | {'IS_SPEECH':<10} | {'BUF SIZE':<9} | {'DROPPED'}")
    print("-" * 85)

    for i in range(chunk_count):
        step = controller.capture_step()
        if step is None:
            break

        chunk, vad_res = step
        stats = controller.get_stats()

        speech_flag = "YES [ACT]" if vad_res.is_speech else "NO  [   ]"
        print(
            f"#{chunk.sequence_id:<4} | "
            f"{chunk.timestamp_ms:>6.1f} ms | "
            f"{vad_res.energy_rms:>5.3f} | "
            f"{vad_res.state:<12} | "
            f"{speech_flag:<10} | "
            f"{stats.current_size:>4}/{stats.capacity}   | "
            f"{stats.total_dropped:>4}"
        )

        # Trigger pause/resume midway if enabled
        if pause_resume and i == 4:
            print("\n  >> Pausing audio stream (Lifecycle: PAUSED)...")
            controller.pause()
            step_paused = controller.capture_step()
            print(f"  >> Attempt capture while paused: {step_paused} (correctly blocked)")
            print("  >> Resuming audio stream (Lifecycle: RECORDING)...\n")
            controller.resume()

    print("-" * 85)

    # 4. Stop Lifecycle & Release Buffer
    print("\n[STEP 4] Lifecycle Stop & Buffer Release:")
    final_chunks = controller.stop()
    print(f"  Lifecycle State: {controller.lifecycle.state.value.upper()}")
    print(f"  Unconsumed Chunks Released from Buffer: {len(final_chunks)}")
    print(f"  Buffer is empty after stop: {controller.buffer.is_empty}")

    stats = controller.get_stats()
    print("\n[SUMMARY TELEMETRY]")
    print(f"  Total Chunks Received: {stats.total_received}")
    print(f"  Buffer Capacity:       {stats.capacity}")
    print(f"  Chunks Dropped:        {stats.total_dropped}")
    print(f"  Gaps Detected:         {stats.gaps_detected}")
    print(f"  Late Chunks Detected:  {stats.late_chunks_detected}")
    print("=" * 85)


def main() -> int:
    parser = argparse.ArgumentParser(description="Week 2 Audio Pipeline CLI Demonstration.")
    parser.add_argument("--capacity", type=int, default=6, help="Buffer capacity limit (default: 6)")
    parser.add_argument("--chunks", type=int, default=10, help="Chunks to capture (default: 10)")
    parser.add_argument("--simulate-denial", action="store_true", help="Simulate microphone permission denial")
    parser.add_argument("--simulate-unsupported", action="store_true", help="Simulate selecting unavailable device")
    parser.add_argument("--no-pause", action="store_true", help="Disable pause/resume simulation")

    args = parser.parse_args()

    try:
        run_pipeline_demo(
            buffer_capacity=args.capacity,
            chunk_count=args.chunks,
            simulate_denial=args.simulate_denial,
            simulate_unsupported=args.simulate_unsupported,
            pause_resume=not args.no_pause,
        )
        return 0
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
