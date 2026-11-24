"""
Timestamped, Source-Linked Observations with Duplicate/Stale Frame Handling and Consent Withdrawal
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 3 / Days 15-16)
Student: Prathibhashree K

Implements:
1. Structured Observation model linking every observation directly to a SourceReference citation and timestamp.
2. Duplicate frame detection and suppression (fingerprinting/hashing to prevent redundant reasoning overhead).
3. Stale frame eviction (discarding observations from outdated frames based on TTL/freshness threshold).
4. Strict consent withdrawal (stops capture, purges cached frames and pending observations immediately).
5. Seamless bridge to ContextItem and BoundedContextBuilder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.context import (
    ScreenContext,
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
    BoundingBox,
)
from .capture_adapter import ScreenCaptureAdapter, CaptureState


class ConsentRevokedError(Exception):
    """Raised when an operation attempts to observe screen context without active user consent."""
    pass


class StaleFrameError(Exception):
    """Raised when an ingested frame is older than the permissible freshness window."""
    pass


@dataclass(frozen=True)
class Observation:
    """
    Atomic, verified observation extracted from screen context.
    Every observation is strictly timestamped and linked to a SourceReference.

    Fields:
    - observation_id (str): Unique UUID v4 string identifying this observation.
    - session_id (str): Active voicebot session identifier.
    - timestamp (str): ISO 8601 UTC timestamp of observation creation.
    - source (SourceReference): Origin citation reference (must be provided and non-null).
    - summary (str): Concise human/LLM-readable synopsis of the visual observation.
    - raw_text (str): Extracted text or structured content backing the observation.
    - confidence (float): Recognition/extraction confidence [0.0 - 1.0].
    - bounding_boxes (List[BoundingBox]): Detected UI elements associated with this observation.
    - is_synthetic (bool): Verifies observation originates from synthetic mock pipeline. Constraint: Always True.
    - metadata (Dict[str, Any]): Additional tags and classification attributes.
    """
    observation_id: str
    session_id: str
    timestamp: str
    source: SourceReference
    summary: str
    raw_text: str
    confidence: float = 1.0
    bounding_boxes: List[BoundingBox] = field(default_factory=list)
    is_synthetic: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        source: SourceReference,
        summary: str,
        raw_text: str,
        confidence: float = 1.0,
        bounding_boxes: Optional[List[BoundingBox]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Observation:
        return cls(
            observation_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source=source,
            summary=summary,
            raw_text=raw_text,
            confidence=confidence,
            bounding_boxes=bounding_boxes or [],
            is_synthetic=True,
            metadata=metadata or {},
        )

    def to_context_item(self, ttl_seconds: Optional[int] = 300) -> ContextItem:
        """
        Converts this Observation into a standard ContextItem for ingestion by BoundedContextBuilder.
        Preserves complete SourceReference citation and timestamp.
        """
        return ContextItem(
            item_id=str(uuid.uuid4()),
            item_type=ContextItemType.SYSTEM_OBSERVATION if hasattr(ContextItemType, "SYSTEM_OBSERVATION") else ContextItemType.OCR_TEXT,
            content=f"Observation: {self.summary}\nEvidence: {self.raw_text}",
            source=self.source,
            confidence=self.confidence,
            created_at=self.timestamp,
            ttl_seconds=ttl_seconds,
            is_synthetic=self.is_synthetic,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "source": self.source.to_dict(),
            "summary": self.summary,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "bounding_boxes": [b.to_dict() for b in self.bounding_boxes],
            "is_synthetic": self.is_synthetic,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Observation:
        boxes = [
            BoundingBox.from_dict(b) if isinstance(b, dict) else b
            for b in data.get("bounding_boxes", [])
        ]
        source = data["source"]
        if isinstance(source, dict):
            source = SourceReference.from_dict(source)
        return cls(
            observation_id=str(data["observation_id"]),
            session_id=str(data["session_id"]),
            timestamp=str(data["timestamp"]),
            source=source,
            summary=str(data["summary"]),
            raw_text=str(data["raw_text"]),
            confidence=float(data.get("confidence", 1.0)),
            bounding_boxes=boxes,
            is_synthetic=bool(data.get("is_synthetic", True)),
            metadata=dict(data.get("metadata", {})),
        )


class ObservationProducer:
    """
    Manages the lifecycle of screen observations:
    - Ingests ScreenContext frames.
    - Validates opt-in consent; halts immediately on consent withdrawal.
    - Detects and drops duplicate frames using content hashing.
    - Detects and drops stale frames exceeding the freshness TTL.
    - Produces timestamped, source-linked Observation records.
    - Maintains a queryable observation buffer with explicit clear capability on consent revocation.
    """

    def __init__(
        self,
        capture_adapter: ScreenCaptureAdapter,
        max_freshness_seconds: float = 60.0,
        dedup_window_seconds: float = 10.0,
    ):
        self.capture_adapter = capture_adapter
        self.max_freshness_seconds = max_freshness_seconds
        self.dedup_window_seconds = dedup_window_seconds

        # Internal storage
        self._observations: List[Observation] = []
        self._last_frame_hash: Optional[str] = None
        self._last_frame_time: Optional[datetime.datetime] = None

        # Telemetry
        self.frames_evaluated: int = 0
        self.observations_produced: int = 0
        self.duplicates_dropped: int = 0
        self.stale_dropped: int = 0
        self.consent_revocation_count: int = 0

    @property
    def has_consent(self) -> bool:
        return self.capture_adapter.has_consent and self.capture_adapter.is_enabled

    def withdraw_consent(self) -> CaptureState:
        """
        Acceptance Criterion:
        Withdrawing consent stops capture and immediately clears all pending
        context, cached frames, and retained observations.
        """
        self.consent_revocation_count += 1
        state = self.capture_adapter.withdraw_consent()
        self.clear_all_observations()
        self._last_frame_hash = None
        self._last_frame_time = None
        return state

    def clear_all_observations(self) -> int:
        """Purges all stored observations from memory."""
        count = len(self._observations)
        self._observations.clear()
        return count

    def get_active_observations(self) -> List[Observation]:
        """Returns all current valid observations."""
        return list(self._observations)

    def compute_frame_hash(self, frame: ScreenContext) -> str:
        """
        Computes a deterministic hash of frame visual semantics (OCR text, window title, bounding boxes)
        to identify identical/duplicate frames.
        """
        box_data = [
            (b.x, b.y, b.width, b.height, b.label)
            for b in sorted(frame.bounding_boxes, key=lambda x: (x.x, x.y))
        ]
        key_content = {
            "window_title": frame.window_title or "",
            "application_name": frame.application_name or "",
            "ocr_text": frame.ocr_text or "",
            "boxes": box_data,
        }
        serialized = json.dumps(key_content, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _parse_timestamp(self, ts_str: str) -> datetime.datetime:
        """Parses ISO timestamp string to UTC datetime."""
        try:
            cleaned = ts_str.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

    def is_frame_stale(
        self,
        frame: ScreenContext,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Determines if a frame exceeds the allowed freshness duration.
        """
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        frame_dt = self._parse_timestamp(frame.timestamp)
        age = (now - frame_dt).total_seconds()
        return age > self.max_freshness_seconds

    def is_frame_duplicate(
        self,
        frame_hash: str,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Checks if this frame is identical to the preceding frame within the dedup window.
        """
        if self._last_frame_hash is None or self._last_frame_time is None:
            return False

        if self._last_frame_hash != frame_hash:
            return False

        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        time_since_last = (now - self._last_frame_time).total_seconds()
        return time_since_last <= self.dedup_window_seconds

    def process_frame(
        self,
        frame: Optional[ScreenContext] = None,
        now: Optional[datetime.datetime] = None,
    ) -> Optional[Observation]:
        """
        Ingests a screen frame, evaluates consent, deduplication, and staleness,
        and produces a timestamped, source-linked Observation.

        Returns:
        - Observation: if frame is fresh, unique, and consent is active.
        - None: if frame is dropped (duplicate, stale) or capture is disabled.

        Raises:
        - ConsentRevokedError: if capture is requested after consent has been withdrawn.
        """
        self.frames_evaluated += 1

        # 1. CONSENT CHECK
        if not self.capture_adapter.has_consent or not self.capture_adapter.is_enabled:
            # Rejection: consent is not granted or was withdrawn
            return None

        # Fetch frame from adapter if not explicitly supplied
        if frame is None:
            frame = self.capture_adapter.capture_frame()

        if frame is None or not frame.capture_enabled or not frame.capture_allowed_by_user:
            return None

        current_time = now or datetime.datetime.now(datetime.timezone.utc)

        # 2. STALENESS CHECK
        if self.is_frame_stale(frame, now=current_time):
            self.stale_dropped += 1
            return None

        # 3. DUPLICATE CHECK
        frame_hash = self.compute_frame_hash(frame)
        if self.is_frame_duplicate(frame_hash, now=current_time):
            self.duplicates_dropped += 1
            return None

        # Update last seen frame hash and time
        self._last_frame_hash = frame_hash
        self._last_frame_time = current_time

        # 4. GENERATE SOURCE-LINKED OBSERVATION
        source_ref = SourceReference(
            source_id=f"src_screen_{frame.context_id[:8]}",
            source_type=SourceType.SYNTHETIC_SCREEN,
            uri=f"synthetic://screen/{frame.session_id}/{frame.context_id}",
            title=frame.window_title or "Synthetic Display Frame",
            snippet=(frame.ocr_text[:200] + "...") if frame.ocr_text and len(frame.ocr_text) > 200 else frame.ocr_text,
            timestamp=frame.timestamp,
        )

        app_name = frame.application_name or "Unknown App"
        win_title = frame.window_title or "Active Screen"
        ocr_preview = (frame.ocr_text or "").strip().replace("\n", " | ")
        summary = f"[{app_name}] {win_title}: {ocr_preview[:120]}"

        observation = Observation(
            observation_id=str(uuid.uuid4()),
            session_id=frame.session_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source=source_ref,
            summary=summary,
            raw_text=frame.ocr_text or "",
            confidence=1.0,
            bounding_boxes=list(frame.bounding_boxes),
            is_synthetic=True,
            metadata={
                "application_name": app_name,
                "window_title": win_title,
                "frame_context_id": frame.context_id,
                "frame_hash": frame_hash,
            },
        )

        self._observations.append(observation)
        self.observations_produced += 1
        return observation
