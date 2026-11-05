"""
Vision and OCR Adapter Interface with Deterministic Mock
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Defines:
- VisionAdapterInterface: Abstract base class for vision and OCR frame processing.
- VisionOCRResult: Structured output schema for extracted text and bounding boxes.
- MockVisionOCRAdapter: Offline, deterministic mock implementation requiring zero external OCR libraries or API keys.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.context import BoundingBox, ScreenContext


@dataclass(frozen=True)
class VisionOCRResult:
    """
    Structured extraction result returned by the vision/OCR adapter.

    Fields:
    - text (str): Extracted text content from visual frame.
    - bounding_boxes (List[BoundingBox]): Spatial coordinates of recognized UI regions.
    - confidence (float): Aggregate OCR recognition confidence ratio [0.0 - 1.0].
    - language (str): Detected primary language code (e.g. 'en').
    - execution_time_ms (float): Processing latency in milliseconds.
    - is_mock (bool): True if generated via mock vision pipeline.
    - metadata (Dict[str, Any]): Additional recognition diagnostics.
    """
    text: str
    bounding_boxes: List[BoundingBox] = field(default_factory=list)
    confidence: float = 1.0
    language: str = "en"
    execution_time_ms: float = 0.0
    is_mock: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "bounding_boxes": [b.to_dict() for b in self.bounding_boxes],
            "confidence": self.confidence,
            "language": self.language,
            "execution_time_ms": self.execution_time_ms,
            "is_mock": self.is_mock,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VisionOCRResult:
        boxes = [
            BoundingBox.from_dict(b) if isinstance(b, dict) else b
            for b in data.get("bounding_boxes", [])
        ]
        return cls(
            text=str(data.get("text", "")),
            bounding_boxes=boxes,
            confidence=float(data.get("confidence", 1.0)),
            language=str(data.get("language", "en")),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
            is_mock=bool(data.get("is_mock", True)),
            metadata=dict(data.get("metadata", {})),
        )


class VisionAdapterInterface(ABC):
    """
    Abstract contract for OCR and computer vision frame analysis.
    """

    @abstractmethod
    def process_frame(self, screen_context: ScreenContext) -> VisionOCRResult:
        """Processes a screen frame, returning structured text, layout, and bounding boxes."""
        raise NotImplementedError

    @abstractmethod
    def extract_text(self, screen_context: ScreenContext) -> str:
        """Extracts textual content from the screen frame."""
        raise NotImplementedError

    @abstractmethod
    def detect_elements(self, screen_context: ScreenContext) -> List[BoundingBox]:
        """Detects interactive and informational visual elements."""
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Returns vision provider operational health and diagnostic status."""
        raise NotImplementedError


class MockVisionOCRAdapter(VisionAdapterInterface):
    """
    Deterministic mock implementation of VisionAdapterInterface.
    Extracts text and UI bounding boxes directly from synthetic frames without external dependencies.
    """

    def __init__(
        self,
        mock_mode: bool = True,
        simulated_latency_ms: float = 5.0,
        default_confidence: float = 0.96,
    ):
        self.mock_mode = mock_mode
        self.simulated_latency_ms = simulated_latency_ms
        self.default_confidence = default_confidence
        self._simulate_failure: bool = False
        self._frames_processed: int = 0

    def set_failure_mode(self, should_fail: bool) -> None:
        """Allows testing error handling in upstream pipelines."""
        self._simulate_failure = should_fail

    def check_health(self) -> Dict[str, Any]:
        status = "degraded" if self._simulate_failure else "healthy"
        return {
            "provider": "MockVisionOCRAdapter",
            "status": status,
            "mock_mode": self.mock_mode,
            "frames_processed": self._frames_processed,
            "simulated_latency_ms": self.simulated_latency_ms,
        }

    def process_frame(self, screen_context: ScreenContext) -> VisionOCRResult:
        start_time = time.perf_counter()

        if self._simulate_failure:
            raise RuntimeError("Vision/OCR adapter simulated hardware or pipeline failure.")

        # Respect privacy boundary: if capture disabled or consent not given, return empty result
        if not screen_context.capture_enabled or not screen_context.capture_allowed_by_user:
            return VisionOCRResult(
                text="",
                bounding_boxes=[],
                confidence=0.0,
                execution_time_ms=0.0,
                is_mock=True,
                metadata={"reason": "capture_disabled"},
            )

        # Enforce synthetic requirement
        if not screen_context.is_synthetic:
            raise ValueError("Privacy violation: Vision OCR adapter only processes synthetic frames.")

        # Extract text and boxes
        extracted_text = screen_context.ocr_text or ""
        boxes = list(screen_context.bounding_boxes)

        # Calculate average confidence across boxes if available
        if boxes:
            avg_conf = sum(b.confidence for b in boxes) / len(boxes)
        else:
            avg_conf = self.default_confidence if extracted_text else 0.0

        if self.simulated_latency_ms > 0:
            time.sleep(self.simulated_latency_ms / 1000.0)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._frames_processed += 1

        return VisionOCRResult(
            text=extracted_text,
            bounding_boxes=boxes,
            confidence=round(avg_conf, 4),
            language="en",
            execution_time_ms=round(elapsed_ms, 2),
            is_mock=True,
            metadata={
                "window_title": screen_context.window_title,
                "application_name": screen_context.application_name,
                "element_count": len(boxes),
            },
        )

    def extract_text(self, screen_context: ScreenContext) -> str:
        res = self.process_frame(screen_context)
        return res.text

    def detect_elements(self, screen_context: ScreenContext) -> List[BoundingBox]:
        res = self.process_frame(screen_context)
        return res.bounding_boxes
