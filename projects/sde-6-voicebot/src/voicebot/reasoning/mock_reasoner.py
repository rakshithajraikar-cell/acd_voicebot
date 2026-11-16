"""
Deterministic Mock Reasoning Engine with Evidence Grounding
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Implements the standard Provider Interface:
- Typed input: ReasoningRequest
- Typed output: ReasoningResult
- Timeout and cancellation support
- Health and status reporting
- Environment configuration with safe mock defaults
- Deterministic output generation
- Evidence grounding with SourceReference citations
- Safe handling of insufficient evidence (surfacing uncertainty)
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.reasoning import (
    ReasoningRequest,
    ReasoningResult,
    ConfidenceLevel,
    ProviderStatus,
)
from contracts.context import SourceReference, SourceType
from ..prompts.prompt_manager import PromptManager


class ReasoningTimeoutError(Exception):
    """Raised when reasoning exceeds the configured deadline."""
    pass


class ReasoningCancelledError(Exception):
    """Raised when a reasoning job is cancelled via cancellation token."""
    pass


class MockReasoningEngine:
    """
    Deterministic mock provider implementing the reasoning pipeline.
    Runs completely offline with zero paid API keys or external services.
    """

    def __init__(
        self,
        mock_mode: Optional[bool] = None,
        default_timeout_ms: int = 5000,
        simulated_delay_ms: float = 10.0,
    ):
        # Configuration read from environment with safe mock defaults
        env_mock = os.getenv("VOICEBOT_MOCK_MODE", "true").lower() in ("true", "1", "yes")
        self.mock_mode: bool = mock_mode if mock_mode is not None else env_mock
        self.default_timeout_ms: int = int(os.getenv("VOICEBOT_REASONING_TIMEOUT_MS", str(default_timeout_ms)))
        self.simulated_delay_ms: float = simulated_delay_ms
        self._status: ProviderStatus = ProviderStatus.HEALTHY
        self._total_requests_served: int = 0

    def check_health(self) -> Dict[str, Any]:
        """
        Provider interface: Reports provider health and operational status.
        """
        return {
            "provider": "MockReasoningEngine",
            "status": self._status.value,
            "mock_mode": self.mock_mode,
            "requests_served": self._total_requests_served,
            "timeout_ms": self.default_timeout_ms,
        }

    def set_status(self, status: ProviderStatus) -> None:
        """Allows testing degraded or unavailable provider states."""
        self._status = status

    def execute_reasoning(
        self,
        request: ReasoningRequest,
        timeout_ms: Optional[int] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> ReasoningResult:
        """
        Core provider method: executes deterministic mock reasoning.
        """
        start_time = time.perf_counter()

        # Check provider status
        if self._status == ProviderStatus.UNAVAILABLE:
            raise RuntimeError("Reasoning provider is currently unavailable.")

        # Check cancellation before starting
        if is_cancelled and is_cancelled():
            raise ReasoningCancelledError("Reasoning operation was cancelled by caller.")

        effective_timeout = timeout_ms or self.default_timeout_ms

        # Render versioned prompt and check for injection attempts
        rendered = PromptManager.render_prompt(
            user_query=request.user_query,
            context_items=request.context_items,
            version=request.prompt_version,
        )

        # Enforce security: if injection detected, refuse immediately with policy notice
        if rendered.injection_detected:
            execution_time = (time.perf_counter() - start_time) * 1000.0
            return ReasoningResult(
                result_id=str(uuid.uuid4()),
                request_id=request.request_id,
                session_id=request.session_id,
                correlation_id=request.correlation_id,
                response_text=(
                    "I cannot process this request because an attempt to override system "
                    "instructions was detected. I must adhere strictly to verified academic guidelines."
                ),
                sources_used=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                has_sufficient_evidence=False,
                uncertainty_reason=f"Security rejection: prompt injection detected ({', '.join(rendered.detected_patterns)}).",
                suggested_action=None,
                prompt_version=request.prompt_version,
                execution_time_ms=execution_time,
                is_mock=True,
            )

        # Check cancellation during execution
        if is_cancelled and is_cancelled():
            raise ReasoningCancelledError("Reasoning operation was cancelled during processing.")

        # Simulate timeout if simulated delay exceeds timeout threshold
        if self.simulated_delay_ms > effective_timeout:
            raise ReasoningTimeoutError(
                f"Reasoning exceeded deadline of {effective_timeout}ms (duration {self.simulated_delay_ms}ms)."
            )

        # Perform deterministic reasoning and grounding
        result = self._evaluate_query_against_context(request)

        execution_time = (time.perf_counter() - start_time) * 1000.0 + self.simulated_delay_ms
        self._total_requests_served += 1

        # Return updated with measured execution time
        return ReasoningResult(
            result_id=result.result_id,
            request_id=result.request_id,
            session_id=result.session_id,
            correlation_id=result.correlation_id,
            response_text=result.response_text,
            sources_used=result.sources_used,
            confidence=result.confidence,
            confidence_level=result.confidence_level,
            has_sufficient_evidence=result.has_sufficient_evidence,
            uncertainty_reason=result.uncertainty_reason,
            suggested_action=result.suggested_action,
            prompt_version=result.prompt_version,
            execution_time_ms=round(execution_time, 2),
            is_mock=True,
        )

    def _evaluate_query_against_context(self, request: ReasoningRequest) -> ReasoningResult:
        """
        Pure deterministic pattern matcher that maps query intents to verified context evidence.
        """
        query_lower = request.user_query.lower()
        context_items = request.context_items

        # Aggregate all text content from active context items
        combined_context = " ".join(item.content for item in context_items)
        combined_lower = combined_context.lower()

        # SCENARIO A: Student Grades queries
        if any(w in query_lower for w in ["grade", "score", "mark", "gpa", "cs101", "math201", "eng102"]):
            # Check if grades information is actually present in context
            if "student academic portal" in combined_lower or "grade:" in combined_lower:
                sources = []
                for item in context_items:
                    if "grade:" in item.content.lower():
                        sources.append(item.source)

                if "cs101" in query_lower:
                    response_text = (
                        "According to your Student Academic Portal, your grade for CS101 "
                        "(Introduction to Computer Science) is A with a score of 94% (4.0 credits)."
                    )
                elif "math201" in query_lower:
                    response_text = (
                        "According to your Student Academic Portal, your grade for MATH201 "
                        "(Multivariable Calculus) is B+ with a score of 88% (4.0 credits)."
                    )
                elif "gpa" in query_lower:
                    response_text = (
                        "Based on your Academic History, your Fall 2026 Semester GPA is 3.72, "
                        "and your academic status is in Good Standing."
                    )
                else:
                    response_text = (
                        "Based on your Academic Portal records, your enrolled courses and grades are: "
                        "CS101: A (94%), MATH201: B+ (88%), and ENG102: A- (91%). Semester GPA: 3.72."
                    )

                return ReasoningResult(
                    result_id=str(uuid.uuid4()),
                    request_id=request.request_id,
                    session_id=request.session_id,
                    correlation_id=request.correlation_id,
                    response_text=response_text,
                    sources_used=sources,
                    confidence=0.96,
                    confidence_level=ConfidenceLevel.HIGH,
                    has_sufficient_evidence=True,
                    uncertainty_reason=None,
                    suggested_action="PROPOSE_VIEW_FULL_TRANSCRIPT",
                    prompt_version=request.prompt_version,
                    execution_time_ms=0.0,
                    is_mock=True,
                )
            else:
                # Insufficient evidence: Asking about grades when screen context has no grades
                return ReasoningResult(
                    result_id=str(uuid.uuid4()),
                    request_id=request.request_id,
                    session_id=request.session_id,
                    correlation_id=request.correlation_id,
                    response_text=(
                        "I cannot find any grade records on your current screen. "
                        "Please open the Student Academic Portal to view your grades."
                    ),
                    sources_used=[],
                    confidence=0.15,
                    confidence_level=ConfidenceLevel.UNKNOWN,
                    has_sufficient_evidence=False,
                    uncertainty_reason="Insufficient evidence: No academic grades data in active screen context.",
                    suggested_action=None,
                    prompt_version=request.prompt_version,
                    execution_time_ms=0.0,
                    is_mock=True,
                )

        # SCENARIO B: Course Schedule / Timetable queries
        if any(w in query_lower for w in ["schedule", "timetable", "class", "lecture", "lab", "office hours"]):
            if "weekly schedule" in combined_lower or "turing hall" in combined_lower:
                sources = [item.source for item in context_items if "schedule" in item.content.lower()]
                if "cs101" in query_lower:
                    response_text = (
                        "Your CS101 Lecture takes place on Monday & Wednesday from 10:00 AM to 11:30 AM "
                        "in Turing Hall Room 302, with lab on Thursday 2:00 PM - 4:00 PM in Computing Lab 4B."
                    )
                else:
                    response_text = (
                        "According to your Fall 2026 Timetable, you have CS101 Lecture on Mon/Wed 10:00-11:30 AM (Room 302) "
                        "and MATH201 on Tue/Thu 9:00-10:30 AM (Room 105)."
                    )

                return ReasoningResult(
                    result_id=str(uuid.uuid4()),
                    request_id=request.request_id,
                    session_id=request.session_id,
                    correlation_id=request.correlation_id,
                    response_text=response_text,
                    sources_used=sources,
                    confidence=0.95,
                    confidence_level=ConfidenceLevel.HIGH,
                    has_sufficient_evidence=True,
                    uncertainty_reason=None,
                    suggested_action="PROPOSE_ADD_REMINDER",
                    prompt_version=request.prompt_version,
                    execution_time_ms=0.0,
                    is_mock=True,
                )
            else:
                return ReasoningResult(
                    result_id=str(uuid.uuid4()),
                    request_id=request.request_id,
                    session_id=request.session_id,
                    correlation_id=request.correlation_id,
                    response_text="I cannot view your course schedule. Please open your University Calendar.",
                    sources_used=[],
                    confidence=0.15,
                    confidence_level=ConfidenceLevel.UNKNOWN,
                    has_sufficient_evidence=False,
                    uncertainty_reason="Insufficient evidence: No schedule details found in screen context.",
                    suggested_action=None,
                    prompt_version=request.prompt_version,
                    execution_time_ms=0.0,
                    is_mock=True,
                )

        # SCENARIO C: Library Loans queries
        if any(w in query_lower for w in ["library", "book", "loan", "borrowed", "due date"]):
            if "campus library" in combined_lower or "due date:" in combined_lower:
                sources = [item.source for item in context_items if "library" in item.content.lower()]
                response_text = (
                    "You have 2 active borrowed books from Campus Library: 'Introduction to Algorithms' "
                    "due Nov 15, 2026, and 'Artificial Intelligence: A Modern Approach' due Nov 22, 2026. Total fines: $0.00."
                )
                return ReasoningResult(
                    result_id=str(uuid.uuid4()),
                    request_id=request.request_id,
                    session_id=request.session_id,
                    correlation_id=request.correlation_id,
                    response_text=response_text,
                    sources_used=sources,
                    confidence=0.94,
                    confidence_level=ConfidenceLevel.HIGH,
                    has_sufficient_evidence=True,
                    uncertainty_reason=None,
                    suggested_action="PROPOSE_RENEW_LOANS",
                    prompt_version=request.prompt_version,
                    execution_time_ms=0.0,
                    is_mock=True,
                )

        # DEFAULT: Insufficient evidence scenario (crucial acceptance criterion)
        return ReasoningResult(
            result_id=str(uuid.uuid4()),
            request_id=request.request_id,
            session_id=request.session_id,
            correlation_id=request.correlation_id,
            response_text=(
                f"I do not have sufficient information in the current screen context to answer: '{request.user_query}'. "
                "Please enable screen context or navigate to the relevant academic window."
            ),
            sources_used=[],
            confidence=0.10,
            confidence_level=ConfidenceLevel.UNKNOWN,
            has_sufficient_evidence=False,
            uncertainty_reason=f"Insufficient evidence: query '{request.user_query}' has no matching records in provided context.",
            suggested_action=None,
            prompt_version=request.prompt_version,
            execution_time_ms=0.0,
            is_mock=True,
        )
