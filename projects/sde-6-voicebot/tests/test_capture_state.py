"""Test capture state exposure for AudioPipelineController."""

from src.audio.controller import AudioPipelineController

def test_capture_state_transitions():
    ctrl = AudioPipelineController()
    assert ctrl.get_capture_state() == "stopped"
    ctrl.start()
    assert ctrl.get_capture_state() == "recording"
    ctrl.pause()
    assert ctrl.get_capture_state() == "paused"
    ctrl.resume()
    assert ctrl.get_capture_state() == "recording"
    ctrl.stop()
    assert ctrl.get_capture_state() == "stopped"
