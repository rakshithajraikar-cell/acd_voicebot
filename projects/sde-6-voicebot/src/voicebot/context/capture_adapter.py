"""
Screen Capture Adapter with Opt-In Privacy Controls
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Implements screen context provider interface with strict privacy controls:
- Capture is strictly OFF by default.
- Explicit user opt-in consent is required before any capture begins.
- Consent can be withdrawn at any time, immediately purging active frames.
- Provides visible indicator status for UI integration (W6).
- Only synthetic frames are served; no OS screenshots or disk storage.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
import datetime

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.context import ScreenContext
from .synthetic_frames import SyntheticFrameGenerator, SyntheticFixture


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
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        # STRICT REQUIREMENT: Disabled by default
        self._capture_enabled: bool = False
        self._user_consent_granted: bool = False
        self._current_fixture: SyntheticFixture = SyntheticFixture.STUDENT_GRADES
        self._last_captured_frame: Optional[ScreenContext] = None

    @property
    def is_enabled(self) -> bool:
        """Returns True only if both consent is granted AND capture is enabled."""
        return self._capture_enabled and self._user_consent_granted

    @property
    def has_consent(self) -> bool:
        return self._user_consent_granted

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
        return CaptureState.ACTIVE

    def disable_capture(self) -> CaptureState:
        """
        Temporarily pauses capture while retaining consent preference.
        """
        self._capture_enabled = False
        self._last_captured_frame = None
        return CaptureState.OFF

    def withdraw_consent(self) -> CaptureState:
        """
        Scenario 3 Acceptance: Withdrawing consent immediately stops capture
        and clears all retained screen context.
        """
        self._user_consent_granted = False
        self._capture_enabled = False
        self._last_captured_frame = None
        return CaptureState.CONSENT_REVOKED

    def set_fixture(self, fixture: SyntheticFixture) -> None:
        """Sets the synthetic fixture to be generated."""
        self._current_fixture = fixture

    def capture_frame(self) -> ScreenContext:
        """
        Captures the next synthetic frame based on active state.
        If capture is off, returns an empty/non-captured ScreenContext.
        """
        if not self.is_enabled:
            # Capture is off: return safe frame with no OCR or visual content
            frame = SyntheticFrameGenerator.generate_screen_context(
                session_id=self.session_id,
                fixture=self._current_fixture,
                capture_allowed_by_user=self._user_consent_granted,
                capture_enabled=False,
            )
            self._last_captured_frame = frame
            return frame

        frame = SyntheticFrameGenerator.generate_screen_context(
            session_id=self.session_id,
            fixture=self._current_fixture,
            capture_allowed_by_user=True,
            capture_enabled=True,
        )
        self._last_captured_frame = frame
        return frame

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
        }
