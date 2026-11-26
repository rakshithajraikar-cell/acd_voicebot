"""Ensure audio pipeline does not write files to disk by default."""
import os
from pathlib import Path
from src.audio.controller import AudioPipelineController

def test_no_disk_write(tmp_path: Path):
    # Run a short session
    ctrl = AudioPipelineController()
    ctrl.start()
    # Simulate a few capture steps
    for _ in range(3):
        ctrl.capture_step()
    ctrl.stop()
    # Check that no audio files were created in the repo root or tmp_path
    repo_root = Path(__file__).parents[2]
    for p in repo_root.rglob('*.wav'):
        assert False, f"Unexpected audio file written: {p}"
    for p in repo_root.rglob('*.raw'):
        assert False, f"Unexpected raw audio file written: {p}"
