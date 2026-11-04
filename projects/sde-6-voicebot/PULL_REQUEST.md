# Pull Request: W4 Agentic Workflow Engine (Week 1 / Days 1–7)

**Title:** `feat(sde6/w4): implement workflow schemas, state machine, mock tools, and executor`  
**Base Branch:** `team/sde-6-voicebot` (or `develop`)  
**Compare Branch:** `feature/w4-workflow-schemas`  
**Author:** Spoorthi Y D (W4 Agentic Workflow Owner, SDE 6)  
**Suggested Reviewer:** Rakshitha J Raikar (SDE 6 Lead) / Peer Reviewer  

---

## 1. Description & Context

This PR delivers the complete **Week 1 (Days 1–7)** foundation and first vertical slice for the **Agentic Workflow Engine (W4)** inside `projects/sde-6-voicebot/`.

### Day-by-Day Implementation:
- **Day 1–2: Schemas & State Machine**
  - Implemented `ToolSpec`, `ApprovalRequest`, `WorkflowStep`, `WorkflowPlan`, and `WorkflowResult` schemas.
  - Implemented `WorkflowStateMachine` governing strictly allowed transitions between `draft`, `awaiting_approval`, `running`, `paused`, `succeeded`, `failed`, and `cancelled`.
  - Enforced terminal state immutability for `succeeded`, `failed`, and `cancelled`.
- **Day 3–4: Harmless Mock Tools & Executor**
  - Created strict allow-list `ToolRegistry` permitting only two harmless mock tools:
    1. `format_notes`: Safe in-memory text structuring (`is_consequential = False`).
    2. `schedule_reminder`: Safe in-memory synthetic reminder (`is_consequential = True`).
  - Built `WorkflowExecutor` supporting topological dependency graph execution.
  - Implemented mandatory human approval gate: Consequential actions default to `awaiting_approval` and never execute unapproved.
  - Rejection strictly prevents tool execution and records a safe audit event.
- **Day 5–6: Automated Test Suite**
  - 57 comprehensive pytest tests covering invalid plans (empty, duplicate IDs, self-dependencies, 2-step and multi-step cycles), illegal state transitions, allow-list violations, and approval gating.
- **Day 7: CLI Demonstration & Documentation**
  - Interactive demonstration script `src/sde6_voicebot/demo.py` showcasing invalid plan rejection, safe tool execution, rejection guarantee, multi-step pipeline execution, and audit timeline.
  - Comprehensive documentation in `README.md`.

---

## 2. Acceptance Criteria Checklist

- [x] **All schemas exist, are defined once, and are documented**: `WorkflowPlan`, `WorkflowStep`, `ToolSpec`, `ApprovalRequest`, `WorkflowResult` defined in `src/sde6_voicebot/contracts/workflow.py`.
- [x] **State machine rejects illegal transitions**: All illegal transitions raise `InvalidStateTransitionError` with context and correlation ID.
- [x] **Only two harmless mock tools exist**: Strictly allow-listed (`format_notes` and `schedule_reminder`); no unrestricted computer control or external sending.
- [x] **Consequential actions default to awaiting approval**: Gated at runtime; unapproved actions never execute.
- [x] **Invalid plans are rejected clearly**: Cycle detection (Kahn's algorithm) and schema validators reject malformed or cyclic plans.
- [x] **Work is on a feature branch**: Committed to `feature/w4-workflow-schemas` branched off `team/sde-6-voicebot`. No direct pushes to `main`.
- [x] **Security & Privacy**: No `.env`, API keys, audio recordings, or personal data committed.

---

## 3. Test Evidence

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: projects/sde-6-voicebot
configfile: pyproject.toml
plugins: anyio-4.13.0
collected 57 items

tests/test_contracts.py::test_session_and_workflow_states_conform_to_spec PASSED
tests/test_contracts.py::test_event_envelope_fields_and_immutability PASSED
tests/test_contracts.py::test_error_envelope_fields_and_redaction PASSED
tests/test_contracts.py::test_tool_spec_and_consequential_default PASSED
tests/test_contracts.py::test_workflow_step_defaults PASSED
tests/test_contracts.py::test_approval_request_schema PASSED
tests/test_executor.py::test_harmless_step_runs_without_approval PASSED
tests/test_executor.py::test_consequential_action_defaults_to_awaiting_approval PASSED
tests/test_executor.py::test_approved_consequential_action_executes_successfully PASSED
tests/test_executor.py::test_rejected_consequential_action_guarantees_no_execution PASSED
tests/test_executor.py::test_multi_step_dependency_chain_with_approval_gate PASSED
tests/test_executor.py::test_step_failure_triggers_workflow_failed_state PASSED
tests/test_invalid_plans.py::test_reject_empty_steps PASSED
tests/test_invalid_plans.py::test_reject_blank_step_id PASSED
tests/test_invalid_plans.py::test_reject_duplicate_step_ids PASSED
tests/test_invalid_plans.py::test_reject_self_dependency PASSED
tests/test_invalid_plans.py::test_reject_non_existent_dependency PASSED
tests/test_invalid_plans.py::test_reject_two_step_cycle PASSED
tests/test_invalid_plans.py::test_reject_multi_step_cycle PASSED
tests/test_invalid_plans.py::test_reject_non_allowlisted_tool_in_executor PASSED
tests/test_mock_tools.py::test_registry_contains_only_two_harmless_tools PASSED
tests/test_mock_tools.py::test_format_notes_spec_is_non_consequential PASSED
tests/test_mock_tools.py::test_schedule_reminder_spec_is_consequential PASSED
tests/test_mock_tools.py::test_format_notes_execution_success PASSED
tests/test_mock_tools.py::test_format_notes_rejects_empty_text PASSED
tests/test_mock_tools.py::test_schedule_reminder_execution_success PASSED
tests/test_mock_tools.py::test_schedule_reminder_rejects_invalid_delay PASSED
tests/test_mock_tools.py::test_schedule_reminder_rejects_invalid_priority PASSED
tests/test_mock_tools.py::test_security_violation_for_unauthorized_tools PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_initial_state_defaults_to_draft PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_legal_happy_path_with_approval PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_legal_direct_running_path PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_legal_pause_resume_cycle PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_legal_rejection_cancellation PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_legal_draft_cancellation PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_legal_failure_transition PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_illegal_transitions_are_rejected [...] (20 variations) PASSED
tests/test_state_machine.py::TestWorkflowStateMachine::test_transition_history_logging PASSED

======================== 57 passed, 1 warning in 0.51s ========================
```

---

## 4. Day 7 Demonstration Output Summary

Running `python src/sde6_voicebot/demo.py`:
- **Scenario 1**: Cycle rejection and unauthorized tool blocking tested and verified.
- **Scenario 2**: Harmless `format_notes` executed directly without approval.
- **Scenario 3**: Consequential `schedule_reminder` paused at `awaiting_approval`. Rejection confirmed that tool result remains `None` (never executed) and state becomes `cancelled`.
- **Scenario 4**: Two-step pipeline (`format_notes` -> `schedule_reminder`) ran Step 1, halted for approval on Step 2, approved by user, executed Step 2, and concluded in `succeeded`.
- **Scenario 5**: Full immutable audit trail of 8 `EventEnvelope` records verified.

---

## 5. Review & Push Instructions

To push this feature branch to GitHub and submit the PR:
```bash
git push origin team/sde-6-voicebot
git push origin feature/w4-workflow-schemas
```
Then navigate to https://github.com/Yashuudevang/acd_voicebot/compare/team/sde-6-voicebot...feature/w4-workflow-schemas and click **Create pull request**.
