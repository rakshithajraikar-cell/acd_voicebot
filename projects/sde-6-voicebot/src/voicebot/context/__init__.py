"""
Screen Context and Synthetic Frame Provider
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K
"""

from .capture_adapter import ScreenCaptureAdapter, CaptureState
from .synthetic_frames import SyntheticFrameGenerator, SyntheticFixture

__all__ = [
    "ScreenCaptureAdapter",
    "CaptureState",
    "SyntheticFrameGenerator",
    "SyntheticFixture",
]
