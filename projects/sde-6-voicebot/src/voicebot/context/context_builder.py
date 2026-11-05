"""
Bounded Context Builder with Recency, Relevance Selection and Stale Filtering
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Implements:
- Stale context pruning based on TTL and timestamps.
- Approximate token budget accounting.
- Multi-factor ranking balancing relevance to user query and item recency.
- Strict token budget bounding to protect LLM context windows.
- Privacy enforcement: only synthetic context items are accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import sys
from pathlib import Path
contracts_path = Path(__file__).resolve().parents[3]
if str(contracts_path) not in sys.path:
    sys.path.insert(0, str(contracts_path))

from contracts.context import ContextItem, SourceReference, SourceType
from ..validation.validators import validate_context_item, ValidationError


@dataclass(frozen=True)
class BoundedContextResult:
    """
    Output payload of the BoundedContextBuilder.

    Fields:
    - selected_items (List[ContextItem]): Context items selected within the token budget.
    - total_tokens (int): Approximated token count of selected items and formatting.
    - token_budget (int): Target token limit requested.
    - dropped_stale_count (int): Number of items dropped due to expired TTL.
    - omitted_budget_count (int): Number of items pruned due to exceeding token budget.
    - formatted_context (str): Structured XML string formatted for prompt injection.
    - metadata (Dict[str, Any]): Telemetry and diagnostics.
    """
    selected_items: List[ContextItem]
    total_tokens: int
    token_budget: int
    dropped_stale_count: int
    omitted_budget_count: int
    formatted_context: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_items": [item.to_dict() for item in self.selected_items],
            "total_tokens": self.total_tokens,
            "token_budget": self.token_budget,
            "dropped_stale_count": self.dropped_stale_count,
            "omitted_budget_count": self.omitted_budget_count,
            "formatted_context": self.formatted_context,
            "metadata": self.metadata,
        }


class BoundedContextBuilder:
    """
    Maintains a buffer of candidate ContextItems and constructs bounded, prioritized context
    for downstream reasoning within hard token constraints.
    """

    def __init__(
        self,
        default_token_budget: int = 1024,
        default_ttl_seconds: int = 300,
        relevance_weight: float = 0.6,
        recency_weight: float = 0.4,
        chars_per_token: float = 4.0,
    ):
        if relevance_weight + recency_weight <= 0:
            raise ValueError("Sum of relevance and recency weights must be positive.")

        self.default_token_budget = default_token_budget
        self.default_ttl_seconds = default_ttl_seconds
        self.relevance_weight = relevance_weight
        self.recency_weight = recency_weight
        self.chars_per_token = chars_per_token

        self._items: List[ContextItem] = []
        self._total_items_ingested: int = 0
        self._total_stale_pruned: int = 0

    def add_item(self, item: ContextItem) -> bool:
        """
        Validates and registers a context item.
        Enforces privacy guarantee: only synthetic items are accepted.
        """
        validated = validate_context_item(item)
        if not validated.is_synthetic:
            raise ValidationError("ContextItem must be marked is_synthetic=True", "is_synthetic", "PRIVACY_VIOLATION")

        self._items.append(validated)
        self._total_items_ingested += 1
        return True

    def add_items(self, items: Iterable[ContextItem]) -> int:
        """Batch ingestion helper."""
        added = 0
        for item in items:
            self.add_item(item)
            added += 1
        return added

    def clear(self) -> None:
        """Purges all stored context items."""
        self._items.clear()

    def get_items(self) -> List[ContextItem]:
        """Returns a copy of all active items."""
        return list(self._items)

    def estimate_tokens(self, text: str) -> int:
        """
        Fast token count approximation based on character heuristic.
        Standard rule of thumb: ~4 characters per token for English text.
        """
        if not text:
            return 0
        return max(1, math.ceil(len(text) / self.chars_per_token))

    def estimate_item_tokens(self, item: ContextItem) -> int:
        """
        Calculates approximate token usage for an entire context item including XML wrapping.
        """
        # Metadata / XML tag overhead: approx 16 tokens
        overhead = 16
        content_tokens = self.estimate_tokens(item.content)
        title_tokens = self.estimate_tokens(item.source.title or "")
        snippet_tokens = self.estimate_tokens(item.source.snippet or "")
        uri_tokens = self.estimate_tokens(item.source.uri or "")

        return overhead + content_tokens + title_tokens + snippet_tokens + uri_tokens

    def _parse_timestamp(self, ts_str: str) -> datetime.datetime:
        """Parses ISO timestamp strings into UTC datetimes."""
        try:
            # Handle standard ISO formats with or without Z
            cleaned = ts_str.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

    def is_stale(
        self,
        item: ContextItem,
        now: Optional[datetime.datetime] = None,
        custom_ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Checks if an item has exceeded its time-to-live threshold.
        """
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        ttl = custom_ttl_seconds if custom_ttl_seconds is not None else item.ttl_seconds
        if ttl is None:
            ttl = self.default_ttl_seconds

        if ttl <= 0:
            return False

        created_dt = self._parse_timestamp(item.created_at)
        age_seconds = (now - created_dt).total_seconds()
        return age_seconds > ttl

    def filter_stale(self, now: Optional[datetime.datetime] = None) -> List[ContextItem]:
        """
        Removes expired items from internal storage and returns the dropped items.
        """
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        retained: List[ContextItem] = []
        dropped: List[ContextItem] = []

        for item in self._items:
            if self.is_stale(item, now):
                dropped.append(item)
            else:
                retained.append(item)

        self._items = retained
        self._total_stale_pruned += len(dropped)
        return dropped

    def calculate_relevance(self, item: ContextItem, query: str) -> float:
        """
        Scores item relevance to user query on a [0.0 - 1.0] scale using term overlap and exact matching.
        """
        if not query or not query.strip():
            return 0.5  # Neutral default if no query specified

        # Tokenize query into alphanumeric terms
        raw_tokens = re.findall(r"\w+", query.lower())
        stopwords = {"what", "is", "my", "the", "a", "an", "for", "in", "on", "at", "to", "and", "or", "show", "me", "tell"}
        query_terms = [t for t in raw_tokens if t not in stopwords]
        if not query_terms:
            query_terms = raw_tokens

        if not query_terms:
            return 0.5

        # Searchable body
        searchable_text = f"{item.content} {item.source.title or ''} {item.source.snippet or ''} {item.source.uri or ''}".lower()

        # Count matched terms
        matches = sum(1 for term in query_terms if term in searchable_text)
        term_overlap = matches / len(query_terms)

        # Bonus for exact query phrase match
        exact_bonus = 0.2 if query.lower().strip() in searchable_text else 0.0

        # Scale by item extraction confidence
        raw_score = (term_overlap * 0.8) + exact_bonus
        final_score = min(1.0, max(0.0, raw_score)) * item.confidence

        return round(final_score, 4)

    def calculate_recency(
        self,
        item: ContextItem,
        now: Optional[datetime.datetime] = None,
    ) -> float:
        """
        Scores item recency on a [0.0 - 1.0] scale decaying with age.
        """
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        ttl = item.ttl_seconds if item.ttl_seconds is not None else self.default_ttl_seconds
        ttl = max(1, ttl)

        created_dt = self._parse_timestamp(item.created_at)
        age_seconds = max(0.0, (now - created_dt).total_seconds())

        # Linear decay normalized over TTL window
        recency = max(0.0, 1.0 - (age_seconds / ttl))
        return round(recency, 4)

    def format_item_to_xml(self, item: ContextItem) -> str:
        """Formats a single ContextItem into XML representation."""
        source_uri = item.source.uri or "synthetic://unknown"
        source_title = item.source.title or "Untitled Source"
        return (
            f'  <context_item id="{item.item_id}" type="{item.item_type.value}" '
            f'confidence="{item.confidence:.2f}" source_uri="{source_uri}">\n'
            f'    <source_title>{source_title}</source_title>\n'
            f'    <content>{item.content}</content>\n'
            f'  </context_item>'
        )

    def build_context(
        self,
        query: str,
        token_budget: Optional[int] = None,
        max_items: Optional[int] = None,
        now: Optional[datetime.datetime] = None,
    ) -> BoundedContextResult:
        """
        Core algorithm:
        1. Filters out stale items.
        2. Scores surviving items using weighted relevance + recency.
        3. Sorts candidate items by combined score in descending order.
        4. Greedily includes items within the hard token budget.
        5. Formats selected items into safe context string.
        """
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        budget = token_budget if token_budget is not None else self.default_token_budget
        if budget <= 0:
            raise ValueError("token_budget must be a positive integer.")

        # Step 1: Filter stale items
        dropped_stale = self.filter_stale(now=now)
        stale_count = len(dropped_stale)

        # Step 2: Score items
        scored_candidates: List[Tuple[float, datetime.datetime, ContextItem, int]] = []
        for item in self._items:
            relevance = self.calculate_relevance(item, query)
            recency = self.calculate_recency(item, now)
            composite_score = (self.relevance_weight * relevance) + (self.recency_weight * recency)
            created_dt = self._parse_timestamp(item.created_at)
            item_tokens = self.estimate_item_tokens(item)
            scored_candidates.append((composite_score, created_dt, item, item_tokens))

        # Step 3: Sort by composite_score descending, then by creation date descending
        scored_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # Step 4: Budget packing
        wrapper_overhead = self.estimate_tokens("<context>\n</context>\n")
        accumulated_tokens = wrapper_overhead
        selected: List[ContextItem] = []
        omitted_budget_count = 0

        for score, dt, item, tokens in scored_candidates:
            if max_items is not None and len(selected) >= max_items:
                omitted_budget_count += 1
                continue

            if accumulated_tokens + tokens <= budget:
                selected.append(item)
                accumulated_tokens += tokens
            else:
                omitted_budget_count += 1

        # Step 5: Format context payload
        if selected:
            # Sort selected chronologically for natural conversational flow
            selected_chronological = sorted(
                selected,
                key=lambda it: self._parse_timestamp(it.created_at)
            )
            item_xml_blocks = [self.format_item_to_xml(it) for it in selected_chronological]
            formatted_context = "<context>\n" + "\n".join(item_xml_blocks) + "\n</context>"
        else:
            formatted_context = "<context>\n  <!-- No valid context items within budget -->\n</context>"

        total_tokens = self.estimate_tokens(formatted_context)

        return BoundedContextResult(
            selected_items=selected,
            total_tokens=total_tokens,
            token_budget=budget,
            dropped_stale_count=stale_count,
            omitted_budget_count=omitted_budget_count,
            formatted_context=formatted_context,
            metadata={
                "query": query,
                "candidates_considered": len(scored_candidates),
                "relevance_weight": self.relevance_weight,
                "recency_weight": self.recency_weight,
                "timestamp": now.isoformat(),
            },
        )

    def get_telemetry(self) -> Dict[str, Any]:
        """Telemetry diagnostics for context builder monitoring."""
        return {
            "total_items_ingested": self._total_items_ingested,
            "total_stale_pruned": self._total_stale_pruned,
            "active_items_count": len(self._items),
            "default_token_budget": self.default_token_budget,
            "default_ttl_seconds": self.default_ttl_seconds,
        }
