"""
Unit Tests for Bounded Context Builder
SDE 6 Voicebot — Workstream W3 (Context and Reasoning)
Student: Prathibhashree K

Verifies:
- Stays strictly within token budget.
- Stale context filtering based on TTL and timestamps.
- Multi-factor scoring prioritizing query relevance and item recency.
- Item token estimation accuracy.
- Privacy rejection of non-synthetic items.
"""

import datetime
import unittest
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from contracts.context import (
    ContextItem,
    ContextItemType,
    SourceReference,
    SourceType,
)
from src.voicebot.context.context_builder import (
    BoundedContextBuilder,
    BoundedContextResult,
)
from src.voicebot.validation.validators import ValidationError


class TestBoundedContextBuilder(unittest.TestCase):

    def setUp(self):
        self.builder = BoundedContextBuilder(
            default_token_budget=200,
            default_ttl_seconds=120,
            relevance_weight=0.7,
            recency_weight=0.3,
        )
        self.now = datetime.datetime.now(datetime.timezone.utc)

    def _create_item(
        self,
        item_id: str,
        content: str,
        age_seconds: float = 0.0,
        ttl_seconds: int = 120,
        is_synthetic: bool = True,
        title: str = "Test Record",
    ) -> ContextItem:
        created_time = self.now - datetime.timedelta(seconds=age_seconds)
        source = SourceReference(
            source_id=f"src-{item_id}",
            source_type=SourceType.SYNTHETIC_SCREEN,
            uri=f"synthetic://screen/{item_id}",
            title=title,
            snippet=content[:50],
            timestamp=created_time.isoformat(),
        )
        return ContextItem(
            item_id=item_id,
            item_type=ContextItemType.OCR_TEXT,
            content=content,
            source=source,
            confidence=0.95,
            created_at=created_time.isoformat(),
            ttl_seconds=ttl_seconds,
            is_synthetic=is_synthetic,
        )

    def test_stale_filtering_drops_expired_items(self):
        """Context items exceeding their TTL are dropped during stale filtering."""
        fresh_item = self._create_item("item-fresh", "Fresh grades CS101: Grade A", age_seconds=10, ttl_seconds=60)
        stale_item = self._create_item("item-stale", "Old outdated schedule", age_seconds=150, ttl_seconds=60)

        self.builder.add_item(fresh_item)
        self.builder.add_item(stale_item)

        result = self.builder.build_context(query="CS101 grade", now=self.now)
        self.assertEqual(result.dropped_stale_count, 1)
        self.assertEqual(len(result.selected_items), 1)
        self.assertEqual(result.selected_items[0].item_id, "item-fresh")

    def test_relevance_selection_prefers_matching_content(self):
        """Items matching the user query are preferred over non-matching items."""
        math_item = self._create_item("item-math", "MATH201 Calculus: Exam on Friday", age_seconds=20)
        grade_item = self._create_item("item-grades", "CS101 Introduction to CS: Score 95% Grade A", age_seconds=20)
        lib_item = self._create_item("item-lib", "Library book borrowed: Algorithms due tomorrow", age_seconds=20)

        self.builder.add_items([math_item, grade_item, lib_item])

        result = self.builder.build_context(query="What is my CS101 score and grade?", max_items=1, now=self.now)
        self.assertEqual(len(result.selected_items), 1)
        self.assertEqual(result.selected_items[0].item_id, "item-grades")

    def test_recency_preference_among_equally_relevant_items(self):
        """When relevance is equal, newer items rank higher than older ones."""
        older_item = self._create_item("item-old", "Office hours in room 302", age_seconds=80)
        newer_item = self._create_item("item-new", "Office hours in room 410", age_seconds=5)

        self.builder.add_items([older_item, newer_item])

        result = self.builder.build_context(query="office hours room", max_items=1, now=self.now)
        self.assertEqual(len(result.selected_items), 1)
        self.assertEqual(result.selected_items[0].item_id, "item-new")

    def test_stays_strictly_within_token_budget(self):
        """Builder never returns context exceeding requested token budget."""
        # Create items with substantial length
        for i in range(10):
            long_content = f"Record {i}: " + ("Detailed course description and assignment rubrics. " * 10)
            item = self._create_item(f"item-{i}", long_content, age_seconds=i * 2)
            self.builder.add_item(item)

        small_budget = 80
        result = self.builder.build_context(query="course description", token_budget=small_budget, now=self.now)

        self.assertLessEqual(result.total_tokens, small_budget)
        self.assertGreater(result.omitted_budget_count, 0)

    def test_rejects_non_synthetic_items(self):
        """Privacy guarantee: Context builder rejects items not marked synthetic."""
        unsafe_item = self._create_item("item-unsafe", "Secret password", is_synthetic=False)
        with self.assertRaises(ValidationError):
            self.builder.add_item(unsafe_item)

    def test_telemetry_reporting(self):
        """Verifies ingestion and pruning telemetry counts."""
        item1 = self._create_item("t1", "Test item 1", age_seconds=5)
        item2 = self._create_item("t2", "Test item 2", age_seconds=200, ttl_seconds=60)
        self.builder.add_items([item1, item2])

        self.builder.build_context(query="Test", now=self.now)
        telemetry = self.builder.get_telemetry()
        self.assertEqual(telemetry["total_items_ingested"], 2)
        self.assertEqual(telemetry["total_stale_pruned"], 1)
        self.assertEqual(telemetry["active_items_count"], 1)


if __name__ == "__main__":
    unittest.main()
