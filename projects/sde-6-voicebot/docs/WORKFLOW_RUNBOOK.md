# Agentic Workflow Engine — Operational Runbook

**Workstream:** W4 (Agentic Workflow Engine)  
**Author:** Spoorthi Y D (`ydspoorthi24-sys`)  
**Target Audience:** SDE 6 Team, SREs, and Platform Operators  
**Release Version:** 1.0.0 (Production Release / Day 30)

---

## 1. Subsystem Architecture Overview

The Agentic Workflow Engine coordinates safe, observable, and recoverable multi-step tool workflows:
- **Contracts (`contracts/workflow.py`)**: Strongly-typed schemas for `WorkflowPlan`, `WorkflowStep`, `ApprovalRequest`, `WorkflowCheckpoint`, `WorkflowResult`.
- **Validation (`workflow/validator.py`)**: Pre-execution DAG cycle detection via Kahn's topological sort, missing dependency checks, tool allow-list verification, argument schema validation, and permission scope enforcement.
- **State Machine (`workflow/state_machine.py`)**: Deterministic transitions (`DRAFT` -> `AWAITING_APPROVAL` <-> `RUNNING` -> `SUCCEEDED` / `FAILED` / `CANCELLED`).
- **Safety Policy Matrix (`workflow/policy_matrix.py`)**: Tool × Risk Level × Approval Gate × Timeout × Permission Scope enforcement.
- **Executor (`workflow/executor.py`)**: Step-level timeouts, bounded idempotent retries, cooperative cancellation, checkpoint snapshotting, and event-envelope audit tracing.
- **Replay Engine (`workflow/replay.py`)**: Deterministic fixture-based verification of recorded workflow traces.

---

## 2. Operational Health & Invariants

| Invariant | Operational Rule | Verification Method |
| :--- | :--- | :--- |
| **Purity of Mock Mode** | Only harmless mock tools (`format_notes`, `schedule_reminder`) exist. Zero external network/file mutations. | `tests/test_mock_tools.py` |
| **Approval Rejection Guarantee** | Rejection strictly guarantees tool execution NEVER occurs (`result=None`, `tool_executed: False`). | `tests/test_failure_injection.py` |
| **Approval Expiry Guarantee** | Expired TTL strictly guarantees tool execution NEVER occurs; rejects late approval attempts. | `tests/test_policy.py` |
| **Idempotency Guard** | Steps with identical `idempotency_key` return cached outputs without invoking tool logic. | `tests/test_week3_integration.py` |
| **Failure Recovery** | Checkpoint restoration resumes failed workflows without re-executing completed steps. | `tests/test_week3_integration.py` |

---

## 3. Standard Operational Procedures (SOPs)

### SOP-01: Starting a Workflow Run
```python
from sde6_voicebot.workflow.executor import WorkflowExecutor
from sde6_voicebot.workflow.tools import ToolRegistry

registry = ToolRegistry(granted_scopes={"safe.memory.read_write", "user.notification.schedule"})
executor = WorkflowExecutor(tool_registry=registry)
result = executor.start_workflow(plan)
```

### SOP-02: Handling Human Approvals via UI
1. Inspect pending approval cards:
   ```python
   ui = UIWorkflowController(executor=executor)
   summary = ui.get_ui_summary()
   pending = summary["pending_approvals"]
   ```
2. Submit user decision:
   ```python
   # To approve:
   ui.submit_approval_decision(request_id=req_id, decision="approve", user_name="alice")
   # To reject:
   ui.submit_approval_decision(request_id=req_id, decision="reject", reason="Declined")
   ```

### SOP-03: Diagnosing & Recovering Failed Workflows
1. Inspect the last checkpoint:
   ```python
   latest_cp = list(executor.checkpoints.values())[-1]
   print(f"Failed steps: {latest_cp.failed_steps}")
   print(f"Completed steps: {latest_cp.completed_steps}")
   ```
2. Resume workflow execution after clearing root cause:
   ```python
   executor.resume_workflow(checkpoint=latest_cp, recover_failed=True)
   ```

### SOP-04: Running Replay Verification
```bash
python -m pytest projects/sde-6-voicebot/tests/test_replay.py -v
```

---

## 4. Error Code Dictionary & Troubleshooting

| Error Code | Meaning | Remediation Action |
| :--- | :--- | :--- |
| `INVALID_WORKFLOW_PLAN` | Cyclic dependency or missing `depends_on` reference. | Check DAG structure; ensure step IDs match dependencies. |
| `UNAUTHORIZED_TOOL_ATTEMPT` | Tool is not registered in the allow-list or Policy Matrix. | Verify tool name against `ToolRegistry.ALLOWED_TOOL_NAMES`. |
| `PERMISSION_SCOPE_DENIED` | Caller lacks the OAuth/security scope required for the tool. | Grant scope in `ToolRegistry(granted_scopes={...})`. |
| `APPROVAL_EXPIRED` | User attempted to approve an action whose TTL elapsed. | Re-generate workflow plan from reasoning; prompt user promptly. |
| `DUPLICATE_APPROVAL_SUBMISSION` | An approval or rejection was already recorded for this request. | Ignore redundant submission; UI should disable action buttons after click. |
| `WORKFLOW_TIMEOUT` | Step execution exceeded `timeout_seconds`. | Investigate slow step handler; adjust timeout if permitted by Policy Matrix. |
| `WORKFLOW_CANCELLED` | An operation was attempted on an already terminated workflow. | Start a fresh workflow plan. |
