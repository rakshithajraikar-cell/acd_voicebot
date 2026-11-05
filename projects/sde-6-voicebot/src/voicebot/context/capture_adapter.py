"""
Screen Capture Adapter with Opt-In Privacy Controls and Sampling/Size Limits
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Implements screen context provider interface with strict privacy controls:
- Capture is strictly OFF by default.
- Explicit user opt-in consent is required before any capture begins.
- Consent can be withdrawn at any time, immediately purging active frames.
- Enforces sampling limits (rate throttling / minimum capture intervals).
- Enforces size limits (maximum display dimensions and payload byte limits).
- Provides visible indicator status for UI integration (W6).
- Only synthetic frames are served; no OS screenshots or disk storage.
"""

from __future__ import annotations

from enum import Enum
import time
from typing import Any, Dict, Optional
import datetime

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.context import ScreenContext
from .synthetic_frames import SyntheticFrameGenerator, SyntheticFixture


class CaptureRateLimitExceededError(Exception):
    """Raised when screen capture requests exceed configured sampling frequency in strict mode."""
    pass


class FrameSizeLimitExceededError(Exception):
    """Raised when captured frame dimensions or payload size exceed configured upper bounds."""
    pass


class CaptureState(str, Enum):
    """
    Visible screen capture indicator state for UI display.
    """
    OFF = "off"
    ACTIVE = "active"
    AWAITING_CONSENT = "awaiting_consent"
    CONSENT_REVOKED = "consent_revoked"


class ScreenCaptureAdapter:
    """
    Adapter managing screen context capture lifecycle.
    Defaults to disabled with zero real screen capture.
    Enforces sampling rate limits and frame size boundaries.
    """

    def __init__(
        self,
        session_id: str,
        min_interval_seconds: float = 0.5,
        max_width: int = 1920,
        max_height: int = 1080,
        max_payload_bytes: int = 5 * 1024 * 1024,
        throttle_policy: str = "cache",
        strict_size_rejection: bool = False,
    ):
        self.session_id = session_id
        # STRICT REQUIREMENT: Disabled by default
        self._capture_enabled: bool = False
        self._user_consent_granted: bool = False
        self._current_fixture: SyntheticFixture = SyntheticFixture.STUDENT_GRADES
        self._last_captured_frame: Optional[ScreenContext] = None
        self._last_capture_timestamp: float = 0.0

        # Sampling limits
        self.min_interval_seconds: float = min_interval_seconds
        self.throttle_policy: str = throttle_policy  # "cache" or "reject"

        # Size limits
        self.max_width: int = max_width
        self.max_height: int = max_height
        self.max_payload_bytes: int = max_payload_bytes
        self.strict_size_rejection: bool = strict_size_rejection

        # Telemetry
        self.captures_attempted: int = 0
        self.captures_completed: int = 0
        self.captures_throttled: int = 0

    @property
    def is_enabled(self) -> bool:
        """Returns True only if both consent is granted AND capture is enabled."""
        return self._capture_enabled and self._user_consent_granted

    @property
    def has_consent(self) -> bool:
        return self._user_consent_granted

    def set_sampling_limits(
        self,
        min_interval_seconds: Optional[float] = None,
        max_sample_rate_hz: Optional[float] = None,
        throttle_policy: Optional[str] = None,
    ) -> None:
        """Configures sampling rate constraints."""
        if max_sample_rate_hz is not None and max_sample_rate_hz > 0:
            self.min_interval_seconds = 1.0 / max_sample_rate_hz
        elif min_interval_seconds is not None:
            self.min_interval_seconds = max(0.0, min_interval_seconds)

        if throttle_policy is not None:
            if throttle_policy not in ("cache", "reject"):
                raise ValueError(f"Unsupported throttle_policy: {throttle_policy}. Must be 'cache' or 'reject'.")
            self.throttle_policy = throttle_policy

    def set_size_limits(
        self,
        max_width: int,
        max_height: int,
        max_payload_bytes: Optional[int] = None,
        strict_size_rejection: Optional[bool] = None,
    ) -> None:
        """Configures maximum permissible frame dimensions and payload size."""
        if max_width <= 0 or max_height <= 0:
            raise ValueError("Max width and height must be strictly positive integers.")
        self.max_width = max_width
        self.max_height = max_height
        if max_payload_bytes is not None:
            self.max_payload_bytes = max_payload_bytes
        if strict_size_rejection is not None:
            self.strict_size_rejection = strict_size_rejection

    def request_consent(self) -> CaptureState:
        """Sets state to awaiting user confirmation."""
        if not self._user_consent_granted:
            return CaptureState.AWAITING_CONSENT
        return CaptureState.ACTIVE if self._capture_enabled else CaptureState.OFF

    def grant_consent_and_enable(self) -> CaptureState:
        """
        User performs explicit action to opt-in to screen context.
        """
        self._user_consent_granted = True
        self._capture_enabled = True
        self._last_captured_frame = None
        self._last_capture_timestamp = 0.0
        return CaptureState.ACTIVE

    def disable_capture(self) -> CaptureState:
        """
        Temporarily pauses capture while retaining consent preference.
        """
        self._capture_enabled = False
        self._last_captured_frame = None
        self._last_capture_timestamp = 0.0
        return CaptureState.OFF

    def withdraw_consent(self) -> CaptureState:
        """
        Scenario 3 Acceptance: Withdrawing consent immediately stops capture
        and clears all retained screen context.
        """
        self._user_consent_granted = False
        self._capture_enabled = False
        self._last_captured_frame = None
        self._last_capture_timestamp = 0.0
        return CaptureState.CONSENT_REVOKED

    def set_fixture(self, fixture: SyntheticFixture) -> None:
        """Sets the synthetic fixture to be generated."""
        if self._current_fixture != fixture:
            self._current_fixture = fixture
            self._last_captured_frame = None
            self._last_capture_timestamp = 0.0

    def _enforce_size_limits(self, frame: ScreenContext) -> ScreenContext:
        """
        Clamps or rejects frame when exceeding size boundaries.
        """
        w, h = frame.screen_width, frame.screen_height
        exceeds_dimensions = (w > self.max_width) or (h > self.max_height)

        payload_bytes = 0
        if frame.ocr_text:
            payload_bytes += len(frame.ocr_text.encode("utf-8"))

        exceeds_payload = payload_bytes > self.max_payload_bytes

        if (exceeds_dimensions or exceeds_payload) and self.strict_size_rejection:
            reason = []
            if exceeds_dimensions:
                reason.append(f"dimensions ({w}x{h}) exceed maximum ({self.max_width}x{self.max_height})")
            if exceeds_payload:
                reason.append(f"payload size ({payload_bytes} bytes) exceeds maximum ({self.max_payload_bytes} bytes)")
            raise FrameSizeLimitExceededError(f"Frame rejected: {', '.join(reason)}")

        if not exceeds_dimensions and not exceeds_payload:
            return frame

        # Downscale / clamp dimensions and payload safely
        clamped_width = min(w, self.max_width)
        clamped_height = min(h, self.max_height)
        adjusted_ocr = frame.ocr_text
        if exceeds_payload and adjusted_ocr:
            adjusted_ocr = adjusted_ocr.encode("utf-8")[:self.max_payload_bytes].decode("utf-8", errors="ignore")

        updated_meta = dict(frame.metadata)
        updated_meta["size_limited"] = True
        updated_meta["original_dimensions"] = f"{w}x{h}"

        return ScreenContext(
            context_id=frame.context_id,
            session_id=frame.session_id,
            timestamp=frame.timestamp,
            capture_enabled=frame.capture_enabled,
            capture_allowed_by_user=frame.capture_allowed_by_user,
            window_title=frame.window_title,
            application_name=frame.application_name,
            screen_width=clamped_width,
            screen_height=clamped_height,
            ocr_text=adjusted_ocr,
            bounding_boxes=frame.bounding_boxes,
            is_synthetic=frame.is_synthetic,
            metadata=updated_meta,
        )

    def capture_frame(self) -> ScreenContext:
        """
        Captures the next synthetic frame based on active state.
        If capture is off, returns an empty/non-captured ScreenContext.
        Enforces sampling rate limit and frame size limits.
        """
        self.captures_attempted += 1
        now = time.monotonic()

        # Check sampling rate limit
        elapsed = now - self._last_capture_timestamp
        if self._last_capture_timestamp > 0 and elapsed < self.min_interval_seconds:
            self.captures_throttled += 1
            if self.throttle_policy == "reject":
                raise CaptureRateLimitExceededError(
                    f"Capture rate limit exceeded: {elapsed:.3f}s elapsed since last capture, "
                    f"minimum interval is {self.min_interval_seconds:.3f}s."
                )
            # Default "cache" policy: return last captured frame if available
            if self._last_captured_frame is not None:
                return self._last_captured_frame

        if not self.is_enabled:
            # Capture is off: return safe frame with no OCR or visual content
            frame = SyntheticFrameGenerator.generate_screen_context(
                session_id=self.session_id,
                fixture=self._current_fixture,
                capture_allowed_by_user=self._user_consent_granted,
                capture_enabled=False,
            )
            bounded_frame = self._enforce_size_limits(frame)
            self._last_captured_frame = bounded_frame
            self._last_capture_timestamp = now
            self.captures_completed += 1
            return bounded_frame

        raw_frame = SyntheticFrameGenerator.generate_screen_context(
            session_id=self.session_id,
            fixture=self._current_fixture,
            capture_allowed_by_user=True,
            capture_enabled=True,
        )
        bounded_frame = self._enforce_size_limits(raw_frame)
        self._last_captured_frame = bounded_frame
        self._last_capture_timestamp = now
        self.captures_completed += 1
        return bounded_frame

    def get_indicator_state(self) -> Dict[str, Any]:
        """
        Telemetry data for frontend capture indicator icon/banner.
        """
        state = CaptureState.OFF
        if self._user_consent_granted and self._capture_enabled:
            state = CaptureState.ACTIVE
        elif not self._user_consent_granted and not self._capture_enabled:
            state = CaptureState.OFF

        return {
            "state": state.value,
            "capture_enabled": self._capture_enabled,
            "user_consent_granted": self._user_consent_granted,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "indicator_color": "green" if state == CaptureState.ACTIVE else "gray",
            "indicator_label": "Screen Context Active (Synthetic)" if state == CaptureState.ACTIVE else "Screen Capture Off",
            "sampling_min_interval_sec": self.min_interval_seconds,
            "max_dimensions": f"{self.max_width}x{self.max_height}",
            "captures_attempted": self.captures_attempted,
            "captures_completed": self.captures_completed,
            "captures_throttled": self.captures_throttled,
        }
