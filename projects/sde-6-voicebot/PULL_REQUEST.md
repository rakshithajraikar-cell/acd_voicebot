# Pull Request: W4 Agentic Workflow — Plan Validation, Tool Registry, Approval Logic & Safe Executor (Week 2 / Days 8–14)

**Title:** `feat(sde6/w4): plan validation, tool registry, approval logic & safe executor (Week 2)`  
**Repository:** `https://github.com/Yashuudevang/acd_voicebot`  
**Base Branch:** `team/sde-6-voicebot` (or `develop`)  
**Compare Branch:** `feature/w4-agentic-workflow`  
**Author:** Spoorthi Y D (W4 Agentic Workflow Owner, Team SDE 6)  
**Suggested Reviewer:** Rakshitha J Raikar (Team SDE 6 Lead)  

---

## 1. Description & Context

This PR delivers the complete **Week 2 (Days 8–14)** requirements for the **Agentic Workflow Engine (W4)** inside `projects/sde-6-voicebot/`. It builds on Week 1 foundations and implements robust safety guarantees: plan validation, DAG cycle detection, an allow-listed tool registry with argument validation and permission scopes, approval logic with TTL expiry, and a safe executor with timeouts, bounded retries for idempotent calls, and cooperative cancellation.

### Day-by-Day Implementation Log:
- **Days 8–9: Dependency and Cycle Validation; Allow-listed Tool Registry with Argument Validation and Permission Scopes**
  - Created `PlanValidator` (`src/sde6_voicebot/workflow/validator.py`) implementing Kahn's topological sort algorithm, referential integrity checks, and cycle tracing with diagnostic reporting.
  - Enhanced `ToolRegistry` (`src/sde6_voicebot/workflow/tools.py`) with strict allow-list enforcement (only `format_notes` and `schedule_reminder` exist).
  - Implemented argument validation (`validate_arguments`) rejecting missing parameters, non-string text, negative delays, and invalid priority enums.
  - Implemented permission scope enforcement (`enforce_permission`) rejecting unauthorized execution attempts with `PermissionScopeError`.
- **Days 10–11: Approve, Reject, and Expiry Logic**
  - Enhanced `ApprovalRequest` with `expires_at`, `ttl_seconds`, and `is_expired()` evaluation.
  - Implemented `approve_step` with pre-flight expiry check, preventing approval of expired actions.
  - Implemented **rejection guarantee**: Rejecting an approval strictly guarantees the tool is NEVER executed (`tool_executed: False`), cancels downstream steps, and transitions workflow to `CANCELLED`.
  - Implemented **expiry guarantee**: Expired approvals strictly guarantee the tool is NEVER executed (`tool_executed: False`), cancel downstream steps, and transition workflow to `CANCELLED`.
- **Days 12–13: Executor Timeouts, Bounded Retries for Idempotent Calls, and Cancellation**
  - Added step execution timeout enforcement (`timeout_seconds`), raising `WorkflowTimeoutError` and emitting `workflow.step_timeout` without hanging.
  - Enforced safety rule for retries: **Retries are bounded by `max_retries` and strictly permitted only for idempotent calls (`is_idempotent=True`)**. Non-idempotent calls (such as `schedule_reminder`) fail immediately on error without retry to prevent duplicate side effects.
  - Implemented cooperative workflow cancellation (`cancel_workflow`) across running and gated states, cancelling pending steps and emitting `workflow.cancelled`.
- **Day 14: Policy Tests, Pull Request, and Demonstrations**
  - Created comprehensive policy test suite `tests/test_policy.py` covering all acceptance criteria. Total passing tests: 125 across the project.
  - Upgraded runnable demonstration script `src/sde6_voicebot/demo.py` showcasing 7 distinct scenarios including approved plan, rejected plan, expired approval, timeouts, bounded retries, and cancellation.

---

## 2. Acceptance Criteria Checklist

- [x] **Plans with cycles or missing dependencies are rejected with clear errors:**
  - Cycle detection via Kahn's algorithm in `PlanValidator` and `WorkflowPlan` identifies cyclic steps.
  - Missing dependencies raise clear `ValueError` / `InvalidPlanError` specifying the missing dependency.
- [x] **Unknown tools and invalid arguments are rejected; permission scopes are enforced:**
  - Non-allowlisted tools raise `ToolSecurityError`.
  - Malformed or missing arguments raise `ToolArgumentError`.
  - Missing permission scopes raise `PermissionScopeError`.
- [x] **A rejected or expired approval guarantees no tool execution and records a safe audit event:**
  - In both rejection and expiry, the tool function is never called, `step.result` remains `None`, downstream steps are cancelled, and `EventEnvelope` records `tool_executed: False`.
- [x] **Executor enforces timeouts; retries are bounded and only for idempotent calls; cancellation works:**
  - Timeouts terminate execution via `WorkflowTimeoutError` and emit `workflow.step_timeout`.
  - Bounded retries up to `max_retries` occur only for idempotent tools (`is_idempotent=True`). Non-idempotent tools never retry.
  - `cancel_workflow()` halts in-flight workflows, marks steps as `CANCELLED`, and emits `workflow.cancelled`.
- [x] **Only harmless mock tools exist; no external sending or computer control:**
  - Exactly two in-memory harmless tools exist: `format_notes` and `schedule_reminder`. No system shell, network, or subprocess calls.
- [x] **No duplicate schemas; tests pass in mock mode:**
  - Reused schemas in `contracts/common.py` and `contracts/workflow.py`. All 125 tests pass in mock mode without external credentials.

---

## 3. Test Evidence

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: projects/sde-6-voicebot
plugins: anyio-4.13.0
collected 125 items

projects/sde-6-voicebot/tests/test_audio_schemas.py .................    [ 13%]
projects/sde-6-voicebot/tests/test_cli.py ......                         [ 18%]
projects/sde-6-voicebot/tests/test_contracts.py ......                   [ 23%]
projects/sde-6-voicebot/tests/test_executor.py ......                    [ 28%]
projects/sde-6-voicebot/tests/test_invalid_plans.py ........             [ 34%]
projects/sde-6-voicebot/tests/test_mock_source.py ...........            [ 43%]
projects/sde-6-voicebot/tests/test_mock_tools.py .........               [ 50%]
projects/sde-6-voicebot/tests/test_policy.py ...............             [ 62%]
projects/sde-6-voicebot/tests/test_state_machine.py .................... [ 78%]
........                                                                 [ 84%]
projects/sde-6-voicebot/tests/test_week2_pipeline.py ................... [100%]

======================= 125 passed, 1 warning in 1.05s ========================
```

---

## 4. Demonstration Run Output

```text
===========================================================================
  ACADEMIAAI AI VOICEBOT - SDE 6 (W4 AGENTIC WORKFLOW WEEK 2 DEMO)
===========================================================================
Author: Spoorthi Y D (W4 Agentic Workflow Owner, SDE 6)
Mode: Mock Mode (Strict Allow-list, No External Calls, Safe Gated Execution)

===========================================================================
  SCENARIO 1: PLAN VALIDATION, CYCLES, ARGUMENTS & PERMISSION SCOPES
===========================================================================
1a. Testing Cyclic Dependency Detection (A -> B -> A)...
  [PASSED] Cycle rejected by validator: Cyclic dependency detected among steps: ['step-a', 'step-b']

1b. Testing Missing Dependency Rejection (Depends on 'ghost-step')...
  [PASSED] Missing dependency rejected: Step 's1' depends on non-existent step 'ghost-step'

1c. Testing Disallowed Tool Blocking ('exec_shell')...
  [PASSED] Non-allowlisted tool blocked: Unauthorized tool 'exec_shell'. Only allow-listed tools ['schedule_reminder', 'format_notes'] are permitted.

1d. Testing Tool Argument Validation (Empty text & negative delay)...
  [PASSED] Invalid text rejected: Argument 'text' must be a non-empty string
  [PASSED] Negative delay rejected: Argument 'delay_minutes' must be a positive integer

1e. Testing Permission Scope Enforcement (Restricted caller)...
  [PASSED] Scope enforcement blocked execution: Permission denied: Tool 'schedule_reminder' requires permission scope 'user.notification.schedule'

===========================================================================
  SCENARIO 2: APPROVED PLAN EXECUTION FLOW
===========================================================================
Initiating plan execution...
Step 1 ('step-1-notes') finished: status=succeeded
Step 2 ('step-2-alert') paused at gate: status=awaiting_approval
Engine State: awaiting_approval

User explicitly approves Request ID: 9cba381a-aea0-4714-a740-81ea5f77eb42...
Pipeline Final State: succeeded
Completed Steps: ['step-1-notes', 'step-2-alert']

===========================================================================
  SCENARIO 3: REJECTED PLAN EXECUTION FLOW (REJECTION GUARANTEE)
===========================================================================
Starting consequential workflow 'Broadcast Workflow (Rejected Flow)'...
Workflow State: awaiting_approval (Awaiting approval)

Simulating user rejection decision: 'Operator denied permission'...
Final Workflow State: cancelled
Step Result (guaranteed None - tool NEVER executed): None
Step Status: cancelled
Step Error Log: Rejected by user: Declined by operator: unauthorized external alert
Audit Log Verified: event_type=workflow.approval_rejected, tool_executed=False

===========================================================================
  SCENARIO 4: EXPIRED APPROVAL FLOW (EXPIRY GUARANTEE)
===========================================================================
Approval Request created with TTL. Waiting for expiration...
Attempting to approve after expiration deadline...
  [PASSED] Approval rejected due to expiry: Approval request expired and cannot be approved
Workflow State: cancelled
Tool executed? False (Guaranteed False)

===========================================================================
  SCENARIO 5: TIMEOUTS & BOUNDED RETRIES FOR IDEMPOTENT CALLS
===========================================================================
Workflow State: succeeded
Retries Attempted: 1 (Bounded by max_retries=2)
Total Invocations: 2

===========================================================================
  SCENARIO 6: WORKFLOW CANCELLATION
===========================================================================
Workflow State before cancel: awaiting_approval
Workflow State after cancel: cancelled
Step Status: cancelled
Pending Approvals Remaining: 0

===========================================================================
  SCENARIO 7: AUDIT EVENT TRAIL INSPECTION (EVENTENVELOPE)
===========================================================================
Audit events emitted for Approved Plan (8 total):
  [1] workflow.initialized         | producer=sde6.workflow_executor
  [2] workflow.step_started        | producer=sde6.workflow_executor
  [3] workflow.step_completed      | producer=sde6.workflow_executor
  [4] workflow.approval_requested  | producer=sde6.workflow_executor
  [5] workflow.approval_granted    | producer=sde6.workflow_executor
  [6] workflow.step_started        | producer=sde6.workflow_executor
  [7] workflow.step_completed      | producer=sde6.workflow_executor
  [8] workflow.completed           | producer=sde6.workflow_executor

===========================================================================
  ALL WEEK 2 AGENTIC WORKFLOW DEMONSTRATIONS COMPLETED SUCCESSFULLY
===========================================================================
```
