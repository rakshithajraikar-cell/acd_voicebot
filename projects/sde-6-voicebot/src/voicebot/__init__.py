"""
SDE 6 Voicebot — Context and Reasoning Subsystem (Workstream W3)
Student: Prathibhashree K
"""

from .context.capture_adapter import (
    ScreenCaptureAdapter,
    CaptureState,
    CaptureRateLimitExceededError,
    FrameSizeLimitExceededError,
)
from .context.synthetic_frames import (
    SyntheticFrameGenerator,
    SyntheticFixture,
)
from .context.vision_adapter import (
    VisionAdapterInterface,
    MockVisionOCRAdapter,
    VisionOCRResult,
)
from .context.context_builder import (
    BoundedContextBuilder,
    BoundedContextResult,
)
from .context.observation_adapter import (
    Observation,
    ObservationProducer,
    ConsentRevokedError,
    StaleFrameError,
)
from .prompts.prompt_manager import (
    PromptManager,
    PromptVersion,
    RenderedPrompt,
    PromptInjectionDetectedError,
)
from .reasoning.mock_reasoner import (
    MockReasoningEngine,
    ReasoningTimeoutError,
    ReasoningCancelledError,
)
from .reasoning.llm_adapter import (
    LLMClientAdapter,
    MockLLMBackend,
    LLMAdapterError,
    LLMTimeoutError,
    LLMRetryExhaustedError,
    MalformedOutputError,
    UnsafeOutputError,
)
from .workflow.handoff import (
    WorkflowHandoffClient,
    MockWorkflowReceiver,
    WorkflowHandoffError,
    validate_workflow_proposal,
    ALLOW_LISTED_TOOLS,
)
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
    # Context & Capture
    "ScreenCaptureAdapter",
    "CaptureState",
    "CaptureRateLimitExceededError",
    "FrameSizeLimitExceededError",
    "SyntheticFrameGenerator",
    "SyntheticFixture",
    # Vision & OCR
    "VisionAdapterInterface",
    "MockVisionOCRAdapter",
    "VisionOCRResult",
    # Bounded Context Builder
    "BoundedContextBuilder",
    "BoundedContextResult",
    # Observations & Consent (Week 3)
    "Observation",
    "ObservationProducer",
    "ConsentRevokedError",
    "StaleFrameError",
    # Prompts & Injection Defense (Week 3)
    "PromptManager",
    "PromptVersion",
    "RenderedPrompt",
    "PromptInjectionDetectedError",
    # Reasoning & LLM
    "MockReasoningEngine",
    "ReasoningTimeoutError",
    "ReasoningCancelledError",
    "LLMClientAdapter",
    "MockLLMBackend",
    "LLMAdapterError",
    "LLMTimeoutError",
    "LLMRetryExhaustedError",
    "MalformedOutputError",
    "UnsafeOutputError",
    # Workflow Handoff (Week 3)
    "WorkflowHandoffClient",
    "MockWorkflowReceiver",
    "WorkflowHandoffError",
    "validate_workflow_proposal",
    "ALLOW_LISTED_TOOLS",
    # Validation & Envelopes
    "ValidationError",
    "validate_reasoning_request",
    "validate_reasoning_result",
    "validate_screen_context",
    "validate_context_item",
    "validate_source_reference",
    "format_error_envelope",
]
