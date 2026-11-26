"""
SDE 6 Voicebot — Context and Reasoning Subsystem (Workstream W3)
Student: Prathibhashree K
"""

from .context.capture_adapter import ScreenCaptureAdapter, CaptureState
from .context.synthetic_frames import SyntheticFrameGenerator, SyntheticFixture
from .prompts.prompt_manager import PromptManager, PromptVersion, RenderedPrompt
from .reasoning.mock_reasoner import MockReasoningEngine, ReasoningTimeoutError, ReasoningCancelledError
from .validation.validators import (
    ValidationError,
    validate_reasoning_request,
    validate_reasoning_result,
    validate_screen_context,
    validate_context_item,
    validate_source_reference,
    format_error_envelope,
)

__all__ = [
    "ScreenCaptureAdapter",
    "CaptureState",
    "SyntheticFrameGenerator",
    "SyntheticFixture",
    "PromptManager",
    "PromptVersion",
    "RenderedPrompt",
    "MockReasoningEngine",
    "ReasoningTimeoutError",
    "ReasoningCancelledError",
    "ValidationError",
    "validate_reasoning_request",
    "validate_reasoning_result",
    "validate_screen_context",
    "validate_context_item",
    "validate_source_reference",
    "format_error_envelope",
]
