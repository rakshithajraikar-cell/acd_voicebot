"""
Tests for Privacy Redaction of Sensitive Screen Text and Credentials
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 4 / Days 25-27)
Student: Prathibhashree K

Acceptance Criteria:
- Redaction tests prove sensitive screen text (emails, tokens and similar)
  is masked before it reaches the prompt or the logs.
"""

import unittest

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_root = project_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from contracts.context import (
    ScreenContext,
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
)
from voicebot.privacy.redactor import TextRedactor
from voicebot.prompts.prompt_manager import PromptManager


class TestPrivacyAndRedaction(unittest.TestCase):
    """
    Validates that PII, secrets, and auth tokens are masked before prompt injection.
    """

    def test_email_redaction(self):
        """Email addresses in text are masked with [EMAIL_REDACTED]."""
        raw = "Contact the instructor at alice.smith99@cs.university.edu for grading questions."
        clean = TextRedactor.redact(raw)
        self.assertNotIn("alice.smith99@cs.university.edu", clean)
        self.assertIn("[EMAIL_REDACTED]", clean)

    def test_api_token_redaction(self):
        """GitHub Personal Access Tokens and API keys are masked."""
        raw_gh = "Current token: ghp_MOCKTESTTOKENFORREDACTION1234567890 configured in env."
        clean_gh = TextRedactor.redact(raw_gh)
        self.assertNotIn("ghp_MOCKTESTTOKENFORREDACTION1234567890", clean_gh)
        self.assertIn("[API_TOKEN_REDACTED]", clean_gh)

        raw_key = "api_key: 'sk_live_99843829482934823948'"
        clean_key = TextRedactor.redact(raw_key)
        self.assertNotIn("sk_live_99843829482934823948", clean_key)
        self.assertIn("[SECRET_REDACTED]", clean_key)

    def test_bearer_token_redaction(self):
        """Bearer tokens and JWT strings are masked."""
        raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeak"
        clean = TextRedactor.redact(raw)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", clean)
        self.assertIn("Bearer [TOKEN_REDACTED]", clean)

    def test_phone_and_ssn_redaction(self):
        """Phone numbers and Social Security Numbers are masked."""
        raw = "Student Emergency Contact: (555) 234-5678, SSN: 123-45-6789."
        clean = TextRedactor.redact(raw)
        self.assertNotIn("(555) 234-5678", clean)
        self.assertNotIn("123-45-6789", clean)
        self.assertIn("[PHONE_REDACTED]", clean)
        self.assertIn("[SSN_REDACTED]", clean)

    def test_prompt_manager_applies_redaction_before_prompting(self):
        """PromptManager automatically masks PII in screen items before building prompt string."""
        sensitive_ocr = (
            "Profile: Bob Jones | Email: bob.jones@mit.edu | Secret Token: ghp_998438294829348239482938472938472938 | "
            "Grades: CS101: A"
        )
        src = SourceReference(
            source_id="src_sensitive",
            source_type=SourceType.SYNTHETIC_SCREEN,
            title="Account Settings: bob.jones@mit.edu",
        )
        item = ContextItem(
            item_id="item_sensitive",
            item_type=ContextItemType.OCR_TEXT,
            content=sensitive_ocr,
            source=src,
        )

        rendered = PromptManager.render_prompt(
            user_query="Who is logged in with email bob.jones@mit.edu?",
            context_items=[item],
            version="1.2.0",
        )

        full_prompt = rendered.full_prompt

        # Raw secrets must NOT be present anywhere in rendered prompt
        self.assertNotIn("bob.jones@mit.edu", full_prompt)
        self.assertNotIn("ghp_998438294829348239482938472938472938", full_prompt)

        # Redacted placeholders must be present
        self.assertIn("[EMAIL_REDACTED]", full_prompt)
        self.assertIn("[API_TOKEN_REDACTED]", full_prompt)


if __name__ == "__main__":
    unittest.main()
