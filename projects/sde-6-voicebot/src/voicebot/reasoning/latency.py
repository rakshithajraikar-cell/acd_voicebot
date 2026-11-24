"""
Per-Stage Latency Instrumentation for Context & Reasoning Pipeline
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 4 / Days 25-27)
Student: Prathibhashree K

Acceptance Criteria:
- Reasoning latency is instrumented per stage, and the numbers are reported.
- Captures granular execution metrics: capture, OCR, context ranking, prompt rendering,
  inference execution, and structured output validation.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import time
from typing import Any, Dict, Iterator, Optional


@dataclass
class StageTiming:
    """Timing measurement for a single pipeline stage."""
    stage_name: str
    duration_ms: float = 0.0
    start_time: float = 0.0


@dataclass
class LatencyReport:
    """
    Consolidated latency report covering all stages of the reasoning lifecycle.

    Fields:
    - capture_ms (float): Screen frame acquisition latency.
    - ocr_ms (float): Optical character recognition / vision extraction latency.
    - context_build_ms (float): Token budgeting, recency scoring, and stale pruning latency.
    - prompt_render_ms (float): Anti-injection scanning, redaction, and XML formatting latency.
    - inference_ms (float): LLM reasoning execution latency.
    - validation_ms (float): Output schema and safety validation latency.
    - total_latency_ms (float): End-to-end total latency.
    """
    capture_ms: float = 0.0
    ocr_ms: float = 0.0
    context_build_ms: float = 0.0
    prompt_render_ms: float = 0.0
    inference_ms: float = 0.0
    validation_ms: float = 0.0
    total_latency_ms: float = 0.0
    custom_stages: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, float]:
        res = {
            "capture_ms": round(self.capture_ms, 3),
            "ocr_ms": round(self.ocr_ms, 3),
            "context_build_ms": round(self.context_build_ms, 3),
            "prompt_render_ms": round(self.prompt_render_ms, 3),
            "inference_ms": round(self.inference_ms, 3),
            "validation_ms": round(self.validation_ms, 3),
            "total_latency_ms": round(self.total_latency_ms, 3),
        }
        for k, v in self.custom_stages.items():
            res[k] = round(v, 3)
        return res


class LatencyTracker:
    """
    Context manager and stopwatch for instrumenting latency across discrete pipeline stages.
    """

    def __init__(self):
        self._stages: Dict[str, float] = {}
        self._pipeline_start: float = time.perf_counter()

    @contextmanager
    def measure(self, stage_name: str) -> Iterator[None]:
        """Measures duration of an arbitrary code block in milliseconds."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            t1 = time.perf_counter()
            duration = (t1 - t0) * 1000.0
            self._stages[stage_name] = self._stages.get(stage_name, 0.0) + duration

    def record_stage(self, stage_name: str, duration_ms: float) -> None:
        """Directly records a measured stage duration."""
        self._stages[stage_name] = max(0.0, float(duration_ms))

    def build_report(self) -> LatencyReport:
        """Computes summary latency metrics from recorded stages."""
        total_wall = (time.perf_counter() - self._pipeline_start) * 1000.0
        capture = self._stages.get("capture", 0.0)
        ocr = self._stages.get("ocr", 0.0)
        ctx = self._stages.get("context_build", 0.0)
        prompt = self._stages.get("prompt_render", 0.0)
        inference = self._stages.get("inference", 0.0)
        validation = self._stages.get("validation", 0.0)

        # Total is max of wall clock or sum of components
        total = self._stages.get("total", max(total_wall, sum([capture, ocr, ctx, prompt, inference, validation])))

        custom = {
            k: v for k, v in self._stages.items()
            if k not in ("capture", "ocr", "context_build", "prompt_render", "inference", "validation", "total")
        }

        return LatencyReport(
            capture_ms=capture,
            ocr_ms=ocr,
            context_build_ms=ctx,
            prompt_render_ms=prompt,
            inference_ms=inference,
            validation_ms=validation,
            total_latency_ms=total,
            custom_stages=custom,
        )
