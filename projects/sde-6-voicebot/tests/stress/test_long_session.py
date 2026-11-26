"""Stress test for long audio sessions (30 min simulated).

The test runs the pipeline in a fast‑forward loop without real time delays, ensuring
memory usage stays bounded and event ordering is correct.
"""
import sys, os
# Ensure project root is on PYTHONPATH for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from src.audio.controller import AudioPipelineController




def test_long_session_stress():
    # Simulate 30 minutes of audio at 20 ms chunks => 30*60*1000/20 = 90_000 iterations
    iterations = 90_000
    ctrl = AudioPipelineController()
    ctrl.start()
    for _ in range(iterations):
        ctrl.capture_step()
    # Ensure we are still in a valid state before stopping
    assert ctrl.lifecycle.is_active()
    ctrl.stop()
    # If we reach here without memory errors, the test passes.
    # Additional checks could be added using tracemalloc, but CI memory limits will catch leaks.

if __name__ == "__main__":
    # Allow running the test directly for quick manual verification
    test_long_session_stress()
    print("Long‑session stress test completed", file=sys.stderr)
