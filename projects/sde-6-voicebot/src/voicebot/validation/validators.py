"""
Schema Validators with ErrorEnvelope Integration
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Implements strict validation logic across all context and reasoning structures.
Translates validation failures directly into standard ErrorEnvelope payloads
(Section 8: code, message_safe_for_user, retryable, correlation_id, details_redacted).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import uuid

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.envelope import ErrorEnvelope
from contracts.context import (
    ScreenContext,
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
    BoundingBox,
)
from contracts.reasoning import (
    ReasoningRequest,
    ReasoningResult,
    ConfidenceLevel,
)


class ValidationError(ValueError):
    """Structured validation failure containing field provenance and code."""
    def __init__(self, message: str, field_name: str, code: str = "INVALID_SCHEMA"):
        super().__init__(f"Validation failed on '{field_name}': {message}")
        self.field_name = field_name
        self.code = code
        self.raw_message = message


def format_error_envelope(
    error: Union[ValidationError, Exception],
    correlation_id: str = "",
    retryable: bool = False,
) -> ErrorEnvelope:
    """
    Transforms any exception into a safe, production-standard ErrorEnvelope.
    """
    if isinstance(error, ValidationError):
        code = error.code
        user_msg = f"Invalid request payload for field '{error.field_name}'. {error.raw_message}"
        details = {"field": error.field_name, "error_type": "ValidationError"}
    else:
        code = "INTERNAL_VALIDATION_ERROR"
        user_msg = "An error occurred while validating the request."
        details = {"error_type": type(error).__name__}

    return ErrorEnvelope(
        code=code,
        message_safe_for_user=user_msg,
        retryable=retryable,
        correlation_id=correlation_id or str(uuid.uuid4()),
        details_redacted=details,
    )


def validate_bounding_box(data: Union[BoundingBox, Dict[str, Any]]) -> BoundingBox:
    box = BoundingBox.from_dict(data) if isinstance(data, dict) else data

    if box.x < 0:
        raise ValidationError("x coordinate must be >= 0", "x", "OUT_OF_BOUNDS")
    if box.y < 0:
        raise ValidationError("y coordinate must be >= 0", "y", "OUT_OF_BOUNDS")
    if box.width <= 0:
        raise ValidationError("width must be > 0", "width", "OUT_OF_BOUNDS")
    if box.height <= 0:
        raise ValidationError("height must be > 0", "height", "OUT_OF_BOUNDS")
    if not box.label or not box.label.strip():
        raise ValidationError("label must be non-empty", "label", "EMPTY_FIELD")
    if not (0.0 <= box.confidence <= 1.0):
        raise ValidationError("confidence must be between 0.0 and 1.0", "confidence", "OUT_OF_RANGE")

    return box


def validate_source_reference(data: Union[SourceReference, Dict[str, Any]]) -> SourceReference:
    source = SourceReference.from_dict(data) if isinstance(data, dict) else data

    if not source.source_id or not source.source_id.strip():
        raise ValidationError("source_id cannot be empty", "source_id", "EMPTY_FIELD")

    if not isinstance(source.source_type, SourceType):
        try:
            SourceType(str(source.source_type))
        except ValueError:
            raise ValidationError(f"Invalid source_type '{source.source_type}'", "source_type", "INVALID_ENUM")

    if source.bounding_box:
        validate_bounding_box(source.bounding_box)

    return source


def validate_context_item(data: Union[ContextItem, Dict[str, Any]]) -> ContextItem:
    item = ContextItem.from_dict(data) if isinstance(data, dict) else data

    if not item.item_id or not item.item_id.strip():
        raise ValidationError("item_id cannot be empty", "item_id", "EMPTY_FIELD")

    if not isinstance(item.item_type, ContextItemType):
        try:
            ContextItemType(str(item.item_type))
        except ValueError:
            raise ValidationError(f"Invalid item_type '{item.item_type}'", "item_type", "INVALID_ENUM")

    if not isinstance(item.content, str) or not item.content.strip():
        raise ValidationError("content must be a non-empty string", "content", "EMPTY_FIELD")

    if not (0.0 <= item.confidence <= 1.0):
        raise ValidationError("confidence must be between 0.0 and 1.0", "confidence", "OUT_OF_RANGE")

    if item.ttl_seconds is not None and item.ttl_seconds < 0:
        raise ValidationError("ttl_seconds must be >= 0", "ttl_seconds", "OUT_OF_RANGE")

    if not item.is_synthetic:
        raise ValidationError("Non-synthetic context items are forbidden in mock mode", "is_synthetic", "PRIVACY_VIOLATION")

    validate_source_reference(item.source)
    return item


def validate_screen_context(data: Union[ScreenContext, Dict[str, Any]]) -> ScreenContext:
    ctx = ScreenContext.from_dict(data) if isinstance(data, dict) else data

    if not ctx.context_id or not ctx.context_id.strip():
        raise ValidationError("context_id cannot be empty", "context_id", "EMPTY_FIELD")

    if not ctx.session_id or not ctx.session_id.strip():
        raise ValidationError("session_id cannot be empty", "session_id", "EMPTY_FIELD")

    if ctx.screen_width <= 0:
        raise ValidationError("screen_width must be positive", "screen_width", "OUT_OF_BOUNDS")

    if ctx.screen_height <= 0:
        raise ValidationError("screen_height must be positive", "screen_height", "OUT_OF_BOUNDS")

    # Strictly verify that real screen capture is not active without synthetic flag
    if not ctx.is_synthetic:
        raise ValidationError("Screen capture must be synthetic in mock mode", "is_synthetic", "PRIVACY_VIOLATION")

    for box in ctx.bounding_boxes:
        validate_bounding_box(box)

    return ctx


def validate_reasoning_request(data: Union[ReasoningRequest, Dict[str, Any]]) -> ReasoningRequest:
    req = ReasoningRequest.from_dict(data) if isinstance(data, dict) else data

    if not req.request_id or not req.request_id.strip():
        raise ValidationError("request_id cannot be empty", "request_id", "EMPTY_FIELD")

    if not req.session_id or not req.session_id.strip():
        raise ValidationError("session_id cannot be empty", "session_id", "EMPTY_FIELD")

    if not req.correlation_id or not req.correlation_id.strip():
        raise ValidationError("correlation_id cannot be empty", "correlation_id", "EMPTY_FIELD")

    if not isinstance(req.user_query, str) or not req.user_query.strip():
        raise ValidationError("user_query must be a non-empty string", "user_query", "EMPTY_FIELD")

    if not (0.0 <= req.temperature <= 1.0):
        raise ValidationError("temperature must be in [0.0, 1.0]", "temperature", "OUT_OF_RANGE")

    if req.max_tokens <= 0:
        raise ValidationError("max_tokens must be > 0", "max_tokens", "OUT_OF_BOUNDS")

    for item in req.context_items:
        validate_context_item(item)

    return req


def validate_reasoning_result(data: Union[ReasoningResult, Dict[str, Any]]) -> ReasoningResult:
    res = ReasoningResult.from_dict(data) if isinstance(data, dict) else data

    if not res.result_id or not res.result_id.strip():
        raise ValidationError("result_id cannot be empty", "result_id", "EMPTY_FIELD")

    if not res.request_id or not res.request_id.strip():
        raise ValidationError("request_id cannot be empty", "request_id", "EMPTY_FIELD")

    if not res.session_id or not res.session_id.strip():
        raise ValidationError("session_id cannot be empty", "session_id", "EMPTY_FIELD")

    if not isinstance(res.response_text, str) or not res.response_text.strip():
        raise ValidationError("response_text must be a non-empty string", "response_text", "EMPTY_FIELD")

    if not (0.0 <= res.confidence <= 1.0):
        raise ValidationError("confidence must be in [0.0, 1.0]", "confidence", "OUT_OF_RANGE")

    if res.execution_time_ms < 0.0:
        raise ValidationError("execution_time_ms must be >= 0.0", "execution_time_ms", "OUT_OF_BOUNDS")

    # If evidence is insufficient, uncertainty_reason must be provided
    if not res.has_sufficient_evidence and not (res.uncertainty_reason and res.uncertainty_reason.strip()):
        raise ValidationError(
            "uncertainty_reason must be specified when has_sufficient_evidence is False",
            "uncertainty_reason",
            "MISSING_UNCERTAINTY_EXPLANATION",
        )

    for src in res.sources_used:
        validate_source_reference(src)

    return res
