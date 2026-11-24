"""Tests for Deterministic Replay Engine (W4).

Verifies that recorded workflow fixtures replay deterministically
and match expected outcomes, state transitions, and completed steps.
"""

from pathlib import Path
import pytest

from sde6_voicebot.workflow.replay import WorkflowReplayEngine


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestReplayEngine:
    def test_replay_happy_path_fixture(self):
        engine = WorkflowReplayEngine()
        fixture_path = FIXTURES_DIR / "replay_happy_path.json"
        data = engine.load_fixture(fixture_path)
        replay_result = engine.replay_from_dict(data)

        assert replay_result["deterministic_match"] is True, f"Mismatches: {replay_result['mismatches']}"
        assert replay_result["result"].final_state.value == "succeeded"
        assert len(replay_result["result"].completed_steps) == 2
        assert "step-1-format" in replay_result["result"].completed_steps
        assert "step-2-reminder" in replay_result["result"].completed_steps

    def test_replay_rejection_fixture(self):
        engine = WorkflowReplayEngine()
        fixture_path = FIXTURES_DIR / "replay_approval_rejection.json"
        data = engine.load_fixture(fixture_path)
        replay_result = engine.replay_from_dict(data)

        assert replay_result["deterministic_match"] is True, f"Mismatches: {replay_result['mismatches']}"
        assert replay_result["result"].final_state.value == "cancelled"
        assert replay_result["result"].completed_steps == ["step-1-format"]
        assert replay_result["result"].failed_steps == ["step-2-reminder"]
        # Tool was strictly NOT executed
        assert "step-2-reminder" not in replay_result["result"].step_results

    def test_replay_single_step_fixture(self):
        engine = WorkflowReplayEngine()
        fixture_path = FIXTURES_DIR / "replay_step_failure_recovery.json"
        data = engine.load_fixture(fixture_path)
        replay_result = engine.replay_from_dict(data)

        assert replay_result["deterministic_match"] is True
        assert replay_result["result"].final_state.value == "succeeded"
        assert replay_result["result"].completed_steps == ["step-1-single"]
