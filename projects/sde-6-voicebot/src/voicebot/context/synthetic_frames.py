"""
Synthetic Frame Fixtures and Generator
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Generates deterministic synthetic screen frames for testing and mock mode reasoning.
PRIVACY & SECURITY GUARANTEES:
- Strictly NO real screenshots or OS window capture.
- Strictly NO personal data, user credentials, or PII.
- Strictly NO disk writes for image frames (in-memory representations only).
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
import datetime
import uuid

import sys
from pathlib import Path
# Add contracts to path if needed
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


class SyntheticFixture(str, Enum):
    """
    Standardized synthetic test scenarios for academia voicebot evaluation.
    """
    STUDENT_GRADES = "student_grades"
    COURSE_SCHEDULE = "course_schedule"
    LIBRARY_LOANS = "library_loans"
    BLANK_DESKTOP = "blank_desktop"


_FIXTURE_DATA: Dict[SyntheticFixture, Dict] = {
    SyntheticFixture.STUDENT_GRADES: {
        "window_title": "Academia Portal — Academic History & Grades",
        "application_name": "MockBrowser",
        "screen_width": 1920,
        "screen_height": 1080,
        "ocr_text": (
            "STUDENT ACADEMIC PORTAL\n"
            "Term: Fall 2026 | Student ID: SYNTH-98421\n"
            "Courses:\n"
            "- CS101: Introduction to Computer Science | Grade: A | Score: 94% | Credits: 4.0\n"
            "- MATH201: Multivariable Calculus | Grade: B+ | Score: 88% | Credits: 4.0\n"
            "- ENG102: Academic Composition | Grade: A- | Score: 91% | Credits: 3.0\n"
            "Semester GPA: 3.72 | Status: Good Standing"
        ),
        "bounding_boxes": [
            BoundingBox(x=100, y=80, width=800, height=60, label="header_title", confidence=0.99),
            BoundingBox(x=100, y=160, width=1200, height=400, label="grades_table", confidence=0.98),
            BoundingBox(x=100, y=580, width=400, height=80, label="gpa_summary", confidence=0.97),
        ],
        "uri": "synthetic://screen/frame_grades_001",
        "title": "Synthetic Student Grades Dashboard",
    },
    SyntheticFixture.COURSE_SCHEDULE: {
        "window_title": "University Calendar — Weekly Timetable",
        "application_name": "MockCalendar",
        "screen_width": 1920,
        "screen_height": 1080,
        "ocr_text": (
            "WEEKLY SCHEDULE — FALL 2026\n"
            "- CS101 Lecture: Monday & Wednesday 10:00 AM - 11:30 AM | Turing Hall Room 302\n"
            "- CS101 Lab: Thursday 2:00 PM - 4:00 PM | Computing Lab 4B\n"
            "- MATH201 Lecture: Tuesday & Thursday 9:00 AM - 10:30 AM | Euler Building Room 105\n"
            "- Office Hours: Friday 11:00 AM - 1:00 PM | Professor Turing Office 410"
        ),
        "bounding_boxes": [
            BoundingBox(x=50, y=50, width=900, height=50, label="calendar_header", confidence=0.99),
            BoundingBox(x=50, y=120, width=1100, height=500, label="schedule_grid", confidence=0.96),
        ],
        "uri": "synthetic://screen/frame_schedule_001",
        "title": "Synthetic Course Timetable",
    },
    SyntheticFixture.LIBRARY_LOANS: {
        "window_title": "Campus Library — Active Resource Loans",
        "application_name": "MockLibraryClient",
        "screen_width": 1920,
        "screen_height": 1080,
        "ocr_text": (
            "CAMPUS LIBRARY CIRCULATION DESK\n"
            "Active Borrowed Items:\n"
            "1. 'Introduction to Algorithms (4th Ed.)' — Due Date: Nov 15, 2026 | Renewal Eligible\n"
            "2. 'Artificial Intelligence: A Modern Approach' — Due Date: Nov 22, 2026 | Renewal Eligible\n"
            "Fines Due: $0.00"
        ),
        "bounding_boxes": [
            BoundingBox(x=80, y=60, width=700, height=70, label="library_header", confidence=0.99),
            BoundingBox(x=80, y=150, width=1000, height=350, label="loans_list", confidence=0.98),
        ],
        "uri": "synthetic://screen/frame_library_001",
        "title": "Synthetic Library Loans Record",
    },
    SyntheticFixture.BLANK_DESKTOP: {
        "window_title": "Desktop",
        "application_name": "DesktopExplorer",
        "screen_width": 1920,
        "screen_height": 1080,
        "ocr_text": "",
        "bounding_boxes": [],
        "uri": "synthetic://screen/frame_blank_001",
        "title": "Empty Desktop Screen",
    },
}


class SyntheticFrameGenerator:
    """
    Deterministic provider of synthetic visual and OCR context frames.
    """

    @staticmethod
    def get_fixture_data(fixture: SyntheticFixture) -> Dict:
        if fixture not in _FIXTURE_DATA:
            raise ValueError(f"Unknown synthetic fixture: {fixture}")
        return _FIXTURE_DATA[fixture]

    @classmethod
    def generate_screen_context(
        cls,
        session_id: str,
        fixture: SyntheticFixture = SyntheticFixture.STUDENT_GRADES,
        capture_allowed_by_user: bool = False,
        capture_enabled: bool = False,
    ) -> ScreenContext:
        """
        Creates a strongly-typed ScreenContext instance from synthetic fixture data.
        Enforces capture_enabled and capture_allowed_by_user flags.
        """
        data = cls.get_fixture_data(fixture)

        # If capture is not enabled, do not expose OCR text or bounding boxes
        ocr_text = data["ocr_text"] if capture_enabled else None
        boxes = data["bounding_boxes"] if capture_enabled else []
        window_title = data["window_title"] if capture_enabled else None
        app_name = data["application_name"] if capture_enabled else None

        return ScreenContext(
            context_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            capture_enabled=capture_enabled,
            capture_allowed_by_user=capture_allowed_by_user,
            window_title=window_title,
            application_name=app_name,
            screen_width=data["screen_width"],
            screen_height=data["screen_height"],
            ocr_text=ocr_text,
            bounding_boxes=boxes,
            is_synthetic=True,
            metadata={"fixture": fixture.value, "environment": "mock"},
        )

    @classmethod
    def generate_context_items(
        cls,
        session_id: str,
        fixture: SyntheticFixture = SyntheticFixture.STUDENT_GRADES,
    ) -> List[ContextItem]:
        """
        Generates contextual items for injection into reasoning requests.
        """
        data = cls.get_fixture_data(fixture)
        if not data["ocr_text"]:
            return []

        source_ref = SourceReference(
            source_id=f"src_{fixture.value}_{uuid.uuid4().hex[:8]}",
            source_type=SourceType.SYNTHETIC_SCREEN,
            uri=data["uri"],
            title=data["title"],
            snippet=data["ocr_text"][:200] + "...",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        item = ContextItem(
            item_id=str(uuid.uuid4()),
            item_type=ContextItemType.OCR_TEXT,
            content=data["ocr_text"],
            source=source_ref,
            confidence=0.98,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ttl_seconds=300,
            is_synthetic=True,
        )
        return [item]
