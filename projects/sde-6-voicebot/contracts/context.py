"""
Context and Screen Capture Schemas
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Defines typed schemas for screen context, context items, and source references.
All schemas are immutable (frozen dataclasses) and include comprehensive field documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import datetime
import uuid


class ContextItemType(str, Enum):
    """
    Categorization of context items ingested into the reasoning pipeline.
    """
    SCREEN_FRAME = "screen_frame"
    OCR_TEXT = "ocr_text"
    ACTIVE_WINDOW = "active_window"
    USER_SELECTION = "user_selection"
    DOCUMENT_SNIPPET = "document_snippet"
    SYSTEM_STATE = "system_state"


class SourceType(str, Enum):
    """
    Origin classification for grounding citations and source references.
    """
    SYNTHETIC_SCREEN = "synthetic_screen"
    USER_PROMPT = "user_prompt"
    MOCK_DOCUMENT = "mock_document"
    SYSTEM_OBSERVATION = "system_observation"


@dataclass(frozen=True)
class BoundingBox:
    """
    Spatial coordinates of a visual element within a synthetic frame.

    Fields:
    - x (int): Horizontal origin coordinate from top-left. Unit: pixels. Constraint: >= 0.
    - y (int): Vertical origin coordinate from top-left. Unit: pixels. Constraint: >= 0.
    - width (int): Width of the bounded region. Unit: pixels. Constraint: > 0.
    - height (int): Height of the bounded region. Unit: pixels. Constraint: > 0.
    - label (str): Semantic label for element (e.g. 'grades_table', 'submit_button'). Constraint: non-empty.
    - confidence (float): Detection confidence score. Unit: ratio [0.0 - 1.0]. Constraint: 0.0 <= confidence <= 1.0.
    """
    x: int
    y: int
    width: int
    height: int
    label: str
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "label": self.label,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BoundingBox:
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            width=int(data["width"]),
            height=int(data["height"]),
            label=str(data["label"]),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass(frozen=True)
class SourceReference:
    """
    Citation metadata pointing to the source of evidence used in a reasoning step.
    Enables explainable, grounded responses and verifies non-hallucination.

    Fields:
    - source_id (str): Unique identifier for this source citation.
    - source_type (SourceType): Classified source origin (e.g. SYNTHETIC_SCREEN).
    - uri (Optional[str]): Synthetic URI or resource locator (e.g. 'synthetic://screen/frame_001').
    - title (Optional[str]): Human-readable title or label of the source (e.g. 'Student Grades Dashboard').
    - snippet (Optional[str]): Verbatim extracted text snippet supporting the reasoning claim.
    - bounding_box (Optional[BoundingBox]): Spatial region on synthetic frame if applicable.
    - timestamp (str): ISO 8601 UTC timestamp when this source was captured/generated.
    """
    source_id: str
    source_type: SourceType
    uri: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value if isinstance(self.source_type, SourceType) else str(self.source_type),
            "uri": self.uri,
            "title": self.title,
            "snippet": self.snippet,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceReference:
        source_type = data["source_type"]
        if isinstance(source_type, str):
            source_type = SourceType(source_type)
        bb = None
        if data.get("bounding_box"):
            bb = BoundingBox.from_dict(data["bounding_box"])
        return cls(
            source_id=str(data["source_id"]),
            source_type=source_type,
            uri=data.get("uri"),
            title=data.get("title"),
            snippet=data.get("snippet"),
            bounding_box=bb,
            timestamp=str(data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())),
        )


@dataclass(frozen=True)
class ScreenContext:
    """
    Structured representation of screen state available for reasoning.

    CRITICAL PRIVACY RULES:
    - `capture_enabled` MUST be False by default.
    - Real screen capture is disabled; only synthetic frames are permitted.
    - `is_synthetic` must be True to prevent accidental leakage of real user data.

    Fields:
    - context_id (str): Unique UUID v4 identifying this screen context capture.
    - session_id (str): Voicebot session identifier.
    - timestamp (str): ISO 8601 UTC timestamp of frame generation.
    - capture_enabled (bool): Whether screen capture is actively enabled. Constraint: Default False.
    - capture_allowed_by_user (bool): Explicit user opt-in consent flag. Constraint: Default False.
    - window_title (Optional[str]): Title of active window (synthetic).
    - application_name (Optional[str]): Name of application (synthetic).
    - screen_width (int): Display width. Unit: pixels. Constraint: > 0.
    - screen_height (int): Display height. Unit: pixels. Constraint: > 0.
    - ocr_text (Optional[str]): Text extracted from synthetic visual frame.
    - bounding_boxes (List[BoundingBox]): Layout annotations for detected UI elements.
    - is_synthetic (bool): Flag confirming frame is mock/synthetic. Constraint: Always True.
    - metadata (Dict[str, Any]): Additional non-sensitive tags and environment metadata.
    """
    context_id: str
    session_id: str
    timestamp: str
    capture_enabled: bool = False
    capture_allowed_by_user: bool = False
    window_title: Optional[str] = None
    application_name: Optional[str] = None
    screen_width: int = 1920
    screen_height: int = 1080
    ocr_text: Optional[str] = None
    bounding_boxes: List[BoundingBox] = field(default_factory=list)
    is_synthetic: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_synthetic(
        cls,
        session_id: str,
        window_title: str,
        application_name: str,
        ocr_text: str,
        bounding_boxes: Optional[List[BoundingBox]] = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
        capture_allowed_by_user: bool = False,
        capture_enabled: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScreenContext:
        return cls(
            context_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            capture_enabled=capture_enabled,
            capture_allowed_by_user=capture_allowed_by_user,
            window_title=window_title,
            application_name=application_name,
            screen_width=screen_width,
            screen_height=screen_height,
            ocr_text=ocr_text,
            bounding_boxes=bounding_boxes or [],
            is_synthetic=True,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "capture_enabled": self.capture_enabled,
            "capture_allowed_by_user": self.capture_allowed_by_user,
            "window_title": self.window_title,
            "application_name": self.application_name,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "ocr_text": self.ocr_text,
            "bounding_boxes": [b.to_dict() for b in self.bounding_boxes],
            "is_synthetic": self.is_synthetic,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScreenContext:
        boxes = [
            BoundingBox.from_dict(b) if isinstance(b, dict) else b
            for b in data.get("bounding_boxes", [])
        ]
        return cls(
            context_id=str(data["context_id"]),
            session_id=str(data["session_id"]),
            timestamp=str(data["timestamp"]),
            capture_enabled=bool(data.get("capture_enabled", False)),
            capture_allowed_by_user=bool(data.get("capture_allowed_by_user", False)),
            window_title=data.get("window_title"),
            application_name=data.get("application_name"),
            screen_width=int(data.get("screen_width", 1920)),
            screen_height=int(data.get("screen_height", 1080)),
            ocr_text=data.get("ocr_text"),
            bounding_boxes=boxes,
            is_synthetic=bool(data.get("is_synthetic", True)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ContextItem:
    """
    Standard atomic item of context ingested by the reasoning layer.

    Fields:
    - item_id (str): Unique UUID v4 identifying this context item.
    - item_type (ContextItemType): Semantic type of the context item.
    - content (str): Textual content, observation, or serialized payload.
    - source (SourceReference): Origin reference for citation and audit trail.
    - confidence (float): Score indicating extraction/recognition quality. Unit: [0.0 - 1.0].
    - created_at (str): ISO 8601 UTC creation timestamp.
    - ttl_seconds (Optional[int]): Time-to-live in seconds for stale context eviction.
    - is_synthetic (bool): Verifies item originates from synthetic mock pipeline.
    """
    item_id: str
    item_type: ContextItemType
    content: str
    source: SourceReference
    confidence: float = 1.0
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    ttl_seconds: Optional[int] = 300
    is_synthetic: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type.value if isinstance(self.item_type, ContextItemType) else str(self.item_type),
            "content": self.content,
            "source": self.source.to_dict(),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "is_synthetic": self.is_synthetic,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContextItem:
        item_type = data["item_type"]
        if isinstance(item_type, str):
            item_type = ContextItemType(item_type)
        source = data["source"]
        if isinstance(source, dict):
            source = SourceReference.from_dict(source)
        return cls(
            item_id=str(data["item_id"]),
            item_type=item_type,
            content=str(data["content"]),
            source=source,
            confidence=float(data.get("confidence", 1.0)),
            created_at=str(data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat())),
            ttl_seconds=int(data["ttl_seconds"]) if data.get("ttl_seconds") is not None else None,
            is_synthetic=bool(data.get("is_synthetic", True)),
        )
