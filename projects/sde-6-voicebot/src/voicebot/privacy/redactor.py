"""
Privacy and Redaction Utility for Screen Text and Logging
SDE 6 Voicebot — Workstream W3 (Context and Reasoning, Week 4 / Days 25-27)
Student: Prathibhashree K

Acceptance Criteria:
- Redaction tests prove sensitive screen text (emails, auth tokens, passwords, API keys)
  is masked before it reaches the prompt, context builder, or logs.
- Safe regex-based redaction preserving non-sensitive layout text while neutralizing secrets.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


class TextRedactor:
    """
    Scans and redacts Personally Identifiable Information (PII) and security credentials
    from screen OCR text, window titles, user queries, and log strings.
    """

    # Compiled patterns for PII and sensitive tokens
    _PATTERNS: List[Tuple[str, re.Pattern[str], str]] = [
        # Email addresses
        (
            "email",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "[EMAIL_REDACTED]",
        ),
        # GitHub Personal Access Tokens / API Tokens
        (
            "token_gh",
            re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,255}\b"),
            "[API_TOKEN_REDACTED]",
        ),
        # Generic Bearer tokens and JWTs
        (
            "bearer_jwt",
            re.compile(r"\bBearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*\b", re.IGNORECASE),
            "Bearer [TOKEN_REDACTED]",
        ),
        # Generic API keys / Secret strings
        (
            "api_key_assigned",
            re.compile(r"(api[_-]?key|secret|password|passwd|auth[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{8,})['\"]?", re.IGNORECASE),
            r"\1: [SECRET_REDACTED]",
        ),
        # Social Security Numbers / National IDs
        (
            "ssn",
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "[SSN_REDACTED]",
        ),
        # Credit Card Numbers
        (
            "credit_card",
            re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
            "[CARD_REDACTED]",
        ),
        # Phone Numbers (standard US / international formats)
        (
            "phone",
            re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"),
            "[PHONE_REDACTED]",
        ),
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        """
        Replaces all sensitive patterns with safe redaction placeholders.
        """
        if not text:
            return ""

        redacted = text
        for name, pattern, replacement in cls._PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    @classmethod
    def redact_and_audit(cls, text: str) -> Tuple[str, List[str]]:
        """
        Redacts text and returns both the sanitized string and a list of detected sensitive types.
        """
        if not text:
            return ("", [])

        detected_types: List[str] = []
        redacted = text
        for name, pattern, replacement in cls._PATTERNS:
            if pattern.search(redacted):
                detected_types.append(name)
                redacted = pattern.sub(replacement, redacted)

        return (redacted, detected_types)
