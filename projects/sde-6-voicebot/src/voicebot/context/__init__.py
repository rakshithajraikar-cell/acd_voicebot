"""
Screen Context, Vision/OCR, Bounded Context and Observations Module
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K
"""

from .capture_adapter import (
    ScreenCaptureAdapter,
    CaptureState,
    CaptureRateLimitExceededError,
    FrameSizeLimitExceededError,
)
from .synthetic_frames import (
    SyntheticFrameGenerator,
    SyntheticFixture,
)
from .vision_adapter import (
    VisionAdapterInterface,
    MockVisionOCRAdapter,
    VisionOCRResult,
)
from .context_builder import (
    BoundedContextBuilder,
    BoundedContextResult,
)
from .observation_adapter import (
    Observation,
    ObservationProducer,
    ConsentRevokedError,
    StaleFrameError,
)

__all__ = [
    "ScreenCaptureAdapter",
    "CaptureState",
    "CaptureRateLimitExceededError",
    "FrameSizeLimitExceededError",
    "SyntheticFrameGenerator",
    "SyntheticFixture",
    "VisionAdapterInterface",
    "MockVisionOCRAdapter",
    "VisionOCRResult",
    "BoundedContextBuilder",
    "BoundedContextResult",
    "Observation",
    "ObservationProducer",
    "ConsentRevokedError",
    "StaleFrameError",
]
