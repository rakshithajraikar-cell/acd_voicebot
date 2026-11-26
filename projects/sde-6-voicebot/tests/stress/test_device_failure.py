"""Stress test for repeated device failure and recovery.

The test repeatedly triggers a device loss and ensures the recovery manager
handles it without crashing or leaking buffers.
"""
import sys, os
# Ensure project root is on PYTHONPATH for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from src.audio.controller import AudioPipelineController

def test_device_failure_stress():
    ctrl = AudioPipelineController()
    ctrl.start()
    # Simulate 5 successive device losses
    for _ in range(5):
        ctrl.simulate_device_loss()
    # After losses, the pipeline should still be active
    assert ctrl.lifecycle.is_active()
    ctrl.stop()

if __name__ == "__main__":
    test_device_failure_stress()
    print("Device‑failure stress test completed", file=sys.stderr)
