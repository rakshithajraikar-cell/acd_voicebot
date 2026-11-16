"""
Reasoning Layer Contracts
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Defines typed schemas for reasoning requests, reasoning results, confidence levels,
and provider status envelopes. Enforces deterministic execution and grounding contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import datetime
import uuid

from .context import ContextItem, SourceReference


class ConfidenceLevel(str, Enum):
    """
    Categorical bucket for reasoning confidence.
    """
    HIGH = "high"        # >= 0.85
    MEDIUM = "medium"    # 0.50 - 0.84
    LOW = "low"          # 0.20 - 0.49
    UNKNOWN = "unknown"  # < 0.20 or no evidence


class ProviderStatus(str, Enum):
    """
    Provider readiness and health status.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ReasoningRequest:
    """
    Canonical request sent to the Reasoning Engine.

    Fields:
    - request_id (str): Unique UUID v4 identifying this reasoning invocation.
    - session_id (str): Voicebot session identifier.
    - correlation_id (str): UUID string for end-to-end tracing across modules.
    - user_query (str): Transcribed user speech or text prompt. Constraint: non-empty.
    - context_items (List[ContextItem]): Active context items (synthetic screen frames, OCR, window info).
    - prompt_version (str): Semantic prompt template version to use (e.g. '1.0.0').
    - temperature (float): Sampling randomness. Constraint: 0.0 <= temperature <= 1.0. Default 0.0 for deterministic mock reasoning.
    - max_tokens (int): Upper bound on generated response length. Constraint: > 0. Default 1024.
    - mock_mode (bool): Flag forcing mock reasoning without external API calls. Constraint: Default True.
    - metadata (Dict[str, Any]): Additional operational tags (e.g. user locale, intent tags).
    """
    request_id: str
    session_id: str
    correlation_id: str
    user_query: str
    context_items: List[ContextItem] = field(default_factory=list)
    prompt_version: str = "1.0.0"
    temperature: float = 0.0
    max_tokens: int = 1024
    mock_mode: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        correlation_id: str,
        user_query: str,
        context_items: Optional[List[ContextItem]] = None,
        prompt_version: str = "1.0.0",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        mock_mode: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReasoningRequest:
        return cls(
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            correlation_id=correlation_id,
            user_query=user_query,
            context_items=context_items or [],
            prompt_version=prompt_version,
            temperature=temperature,
            max_tokens=max_tokens,
            mock_mode=mock_mode,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "user_query": self.user_query,
            "context_items": [item.to_dict() for item in self.context_items],
            "prompt_version": self.prompt_version,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "mock_mode": self.mock_mode,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReasoningRequest:
        items = [
            ContextItem.from_dict(item) if isinstance(item, dict) else item
            for item in data.get("context_items", [])
        ]
        return cls(
            request_id=str(data["request_id"]),
            session_id=str(data["session_id"]),
            correlation_id=str(data["correlation_id"]),
            user_query=str(data["user_query"]),
            context_items=items,
            prompt_version=str(data.get("prompt_version", "1.0.0")),
            temperature=float(data.get("temperature", 0.0)),
            max_tokens=int(data.get("max_tokens", 1024)),
            mock_mode=bool(data.get("mock_mode", True)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ReasoningResult:
    """
    Schema-validated output returned by the Reasoning Engine.

    Fields:
    - result_id (str): Unique UUID v4 identifying this result.
    - request_id (str): Correlating request_id that produced this result.
    - session_id (str): Voicebot session identifier.
    - correlation_id (str): Tracing ID propagated from request.
    - response_text (str): Grounded, factual response or uncertainty statement.
    - sources_used (List[SourceReference]): Citations to the specific context items backing the response.
    - confidence (float): Numerical confidence score in range [0.0 - 1.0].
    - confidence_level (ConfidenceLevel): Categorical confidence bucket.
    - has_sufficient_evidence (bool): Flag indicating whether supporting context was sufficient.
    - uncertainty_reason (Optional[str]): Explanation if evidence is insufficient (surfaces uncertainty).
    - suggested_action (Optional[str]): Optional follow-up action or workflow proposal.
    - prompt_version (str): Prompt version used during reasoning.
    - execution_time_ms (float): Execution latency in milliseconds. Constraint: >= 0.0.
    - is_mock (bool): True if generated via mock engine. Constraint: True.
    """
    result_id: str
    request_id: str
    session_id: str
    correlation_id: str
    response_text: str
    sources_used: List[SourceReference] = field(default_factory=list)
    confidence: float = 1.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    has_sufficient_evidence: bool = True
    uncertainty_reason: Optional[str] = None
    suggested_action: Optional[str] = None
    prompt_version: str = "1.0.0"
    execution_time_ms: float = 0.0
    is_mock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "response_text": self.response_text,
            "sources_used": [s.to_dict() for s in self.sources_used],
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value if isinstance(self.confidence_level, ConfidenceLevel) else str(self.confidence_level),
            "has_sufficient_evidence": self.has_sufficient_evidence,
            "uncertainty_reason": self.uncertainty_reason,
            "suggested_action": self.suggested_action,
            "prompt_version": self.prompt_version,
            "execution_time_ms": self.execution_time_ms,
            "is_mock": self.is_mock,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReasoningResult:
        sources = [
            SourceReference.from_dict(s) if isinstance(s, dict) else s
            for s in data.get("sources_used", [])
        ]
        conf_level = data.get("confidence_level", ConfidenceLevel.HIGH)
        if isinstance(conf_level, str):
            conf_level = ConfidenceLevel(conf_level)
        return cls(
            result_id=str(data["result_id"]),
            request_id=str(data["request_id"]),
            session_id=str(data["session_id"]),
            correlation_id=str(data["correlation_id"]),
            response_text=str(data["response_text"]),
            sources_used=sources,
            confidence=float(data.get("confidence", 1.0)),
            confidence_level=conf_level,
            has_sufficient_evidence=bool(data.get("has_sufficient_evidence", True)),
            uncertainty_reason=data.get("uncertainty_reason"),
            suggested_action=data.get("suggested_action"),
            prompt_version=str(data.get("prompt_version", "1.0.0")),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
            is_mock=bool(data.get("is_mock", True)),
        )
