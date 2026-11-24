# Academiaai AI Voicebot — Team SDE 6

Welcome to the team project repository for **Academiaai AI Voicebot — Team SDE 6**.
All team work is organized by workstream within `projects/sde-6-voicebot/` following the shared engineering standards.

---

## 1. Team & Workstream Structure

- **Repository:** `https://github.com/Yashuudevang/acd_voicebot`
- **Target Branch:** `team/sde-6-voicebot` (or `develop`)
- **Workstreams:**
  - **W1 — Audio & Voice Activity Detection:** Rakshitha J Raikar (`feature/w1-audio-schemas`, `feature/w2-audio-lifecycle-vad`)
  - **W2 — Speech-to-Text:** Pavithra P
  - **W3 — Context, Vision & Reasoning:** Prathibhashree K (`feature/w3-context-schemas`)
  - **W4 — Agentic Workflow Engine:** Spoorthi Y D (`feature/w4-agentic-workflow`)
  - **W5 — Backend, Sessions & Observability:** Radhika B
  - **W6 — Frontend & User Experience:** Shivani Adaragunchi

---

## 2. Workstream W1: Audio & VAD Architecture

```
+---------------------------------------------------------------------------------+
|                        W1 AUDIO PIPELINE ARCHITECTURE                           |
|                                                                                 |
|  [MockAudioDeviceAdapter]                                                       |
|   - Permission validation: GRANTED, DENIED, PROMPT                              |
|   - AudioFormat negotiation (8kHz - 48kHz, mono/stereo)                         |
|           │                                                                     |
|           ▼                                                                     |
|  [MockMicrophoneSource] ---> [DeterministicAudioChunker]                        |
|   - Deterministic sine waveform     - Monotonic sequence IDs                    |
|   - Zero hardware dependency        - Accurate timestamps                       |
|           │                                                                     |
|           ▼                                                                     |
|  [AudioLifecycleController]                                                     |
|   - States: CREATED -> RECORDING <-> PAUSED -> STOPPED                          |
|   - Rejects illegal state transitions with AudioError                           |
|   - Flushes/releases buffer on stop hook                                        |
|           │                                                                     |
|           ▼                                                                     |
|  [VoiceActivityDetector (EnergyVAD)]                                            |
|   - Configurable energy threshold and minimum speech duration (noise filter)    |
|   - Hangover duration smoothing                                                 |
|   - Deterministic classification on fixtures                                    |
|           │                                                                     |
|           ▼                                                                     |
|  [BoundedAudioBuffer]                                                           |
|   - Bounded capacity with backpressure policies (DROP_OLDEST, DROP_NEWEST)      |
|   - Dropped-chunk telemetry counter                                             |
|   - Gap and late-arrival detection                                              |
|           │                                                                     |
|           ▼                                                                     |
|  [Downstream Consumers (W2: Speech-to-Text)]                                    |
+---------------------------------------------------------------------------------+
```

---

## 3. Workstream W3: Context and Reasoning Layer Architecture

This subsystem provides typed schemas, privacy-preserving synthetic frame generation, versioned prompt management, deterministic mock reasoning, and a strict validation engine.
Everything operates completely in **mock mode** with zero paid API keys, zero external network calls, zero disk writes for frames, and zero real personal data.

### W3 Schemas (`contracts/context.py`, `contracts/reasoning.py`):
- `ScreenContext`: Screen geometry, OCR text, bounding boxes, opt-in privacy consent.
- `ContextItem`: Item type, source references, confidence ratio, TTL expiration.
- `SourceReference`: Provenance citations (`synthetic://screen/frame_001`).
- `ReasoningRequest` & `ReasoningResult`: Grounded responses, citations, confidence levels, uncertainty surfacing, and suggested actions.

---

## 4. Workstream W4: Agentic Workflow Engine (Weeks 1–3)

- **Assignee:** Spoorthi Y D
- **Feature Branch:** `feature/w4-agentic-workflow`
- **Base Branch:** `team/sde-6-voicebot`

### Architecture Overview

```
                                  [ WorkflowPlan ]
                                         │
                                         ▼
                                  [ PlanValidator ]
                                   - Step ID uniqueness & non-blank
                                   - Referential integrity of depends_on
                                   - Kahn's DAG cycle detection
                                   - Tool allow-list & parameter schema
                                   - Permission scope authorization
                                         │
                                         ▼
                              [ WorkflowStateMachine ]
          draft ───► awaiting_approval ───► running ───► succeeded
            │                │                 │             (terminal)
            │                │                 ├───► failed (terminal)
            └────────────────┴─────────────────┴───► cancelled (terminal)
                                         │
                                         ▼
                              [ WorkflowExecutor ]
             ┌───────────────────────────┴───────────────────────────┐
             ▼                                                       ▼
   [ Harmless / Approved Step ]                             [ Consequential Step ]
             │                                                       │
             ▼                                                       ▼
   [ ToolRegistry Allow-list ]                             [ Approval Gate & TTL ]
    - format_notes (safe, idempotent)                       - PENDING -> APPROVED
    - schedule_reminder (consequential)                     - REJECTED -> guarantees NO execution
    - Permission scope check                                - EXPIRED  -> guarantees NO execution
             │                                                       │
             ▼                                                       ▼
   [ Execution Engine ]                                     [ Safe Cancellation ]
    - Timeouts (step_timeout_seconds)                        - Downstream steps cancelled
    - Bounded retries (idempotent calls ONLY)                - Immutable audit events
    - Cancellation handling                                  - Tool NEVER executed
    - Checkpoint & resume on failure                         - Idempotency store cache
```

### Key Modules & Deliverables (W4)

All W4 code is self-contained within `projects/sde-6-voicebot/src/sde6_voicebot/`:

1. **Contracts (`contracts/common.py`, `contracts/workflow.py`)**:
   - `WorkflowPlan`: Strongly typed plan model with Kahn's DAG cycle detection and dependency referential integrity.
   - `WorkflowStep`: Step specification with `timeout_seconds`, `max_retries`, `retry_count`, `is_idempotent`, and optional `idempotency_key`.
   - `ToolSpec`: Specification declaring `is_consequential`, `is_idempotent`, and required `permission_scope`.
   - `ApprovalRequest`: Human approval request schema with `expires_at`, `ttl_seconds`, and `is_expired()` evaluation.
   - `WorkflowResult`: Immutable execution outcome with `completed_steps`, `step_results`, `audit_events`, and redacted error envelope.
   - `EventEnvelope` & `ErrorEnvelope`: Standardized envelopes for audit tracing and safe error exposure.

2. **Plan Validation (`workflow/validator.py`)**:
   - `PlanValidator`: Validates structural integrity, dependency graphs, cycle detection via Kahn's algorithm with explicit cycle path reporting, tool allow-list validation, argument validation against parameter schemas, and permission scope authorization.

3. **Tool Registry & Permission Scopes (`workflow/tools.py`)**:
   - Strict allow-list containing **only harmless mock tools**:
     - `format_notes`: Safe in-memory text structuring (`is_consequential=False`, `is_idempotent=True`, scope: `safe.memory.read_write`).
     - `schedule_reminder`: Safe in-memory synthetic reminder (`is_consequential=True`, `is_idempotent=False`, scope: `user.notification.schedule`).
   - `ToolRegistry.validate_arguments()`: Validates types, required fields, and boundary constraints.
   - `ToolRegistry.enforce_permission()`: Rejects unauthorized callers lacking the required permission scope with `PermissionScopeError`.

4. **Approval Logic & Guarantees (`workflow/executor.py`)**:
   - Gating: Consequential actions default to `awaiting_approval` and halt execution until explicit human decision.
   - **Rejection Guarantee:** Rejecting an approval strictly guarantees the tool is NEVER executed (`tool_executed: False`), marks the step as cancelled, cancels downstream steps, transitions workflow to `CANCELLED`, and emits a safe audit event.
   - **Expiry Guarantee:** Expiration of an approval request (via TTL) guarantees the tool is NEVER executed, rejects late approval attempts with `ApprovalExpiredError`, cancels downstream steps, and records a safe audit event.

5. **Safe Executor Engine (`workflow/executor.py`)**:
   - **Timeouts:** Enforces execution timeouts (`timeout_seconds`), catching hanging or slow operations with `WorkflowTimeoutError` and emitting `workflow.step_timeout`.
   - **Bounded Retries:** Restricts retries strictly to **idempotent** calls (`is_idempotent=True`), retrying up to `max_retries`. Non-idempotent calls are strictly blocked from retrying to prevent duplicate side effects.
   - **Cancellation:** Supports immediate cancellation via `cancel_workflow(reason)` across all non-terminal states, halting steps and releasing pending approvals.
   - **Checkpoint & Resume:** Supports persisting state snapshots and resuming paused or recovered workflows without re-running completed steps.

---

## 5. Demonstrations

### Week 2 & Week 3 Agentic Workflow Demo:
```bash
python projects/sde-6-voicebot/src/sde6_voicebot/demo.py
```

### Audio Stream Demonstrations:
```bash
# Week 1 CLI Stream Demo
python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --count 10

# Week 2 Pipeline & VAD Demo
python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py
```

### Context & Reasoning Vertical Slice Demo:
```bash
python projects/sde-6-voicebot/demo/demo_grounded_response.py
```

---

## 6. Test Suite Execution

Run all automated unit, contract, and policy tests:
```bash
python -m pytest projects/sde-6-voicebot/tests/ -v
```

---

## 7. Acceptance Criteria Checklist (W4 Agentic Workflow)

- [x] **Cycle and dependency validation:** Plans with cycles or missing dependencies are rejected with clear errors identifying the offending steps.
- [x] **Tool allow-list & argument validation:** Unknown tools raise `ToolSecurityError`; invalid arguments raise `ToolArgumentError`.
- [x] **Permission scopes enforcement:** Caller lacking the tool's required permission scope is rejected with `PermissionScopeError`.
- [x] **Approval rejection guarantee:** A rejected approval guarantees no tool execution (`step.result is None`), cancels downstream steps, and records a safe audit event with `tool_executed: False`.
- [x] **Approval expiry guarantee:** An expired approval guarantees no tool execution, rejects late approval attempts, cancels downstream steps, and records a safe audit event.
- [x] **Executor timeouts:** Step timeouts are enforced via `timeout_seconds`, safely terminating hanging operations.
- [x] **Bounded retries for idempotent calls:** Retries are bounded by `max_retries` and strictly permitted only for idempotent calls. Non-idempotent calls are never retried.
- [x] **Workflow cancellation:** Cleanly halts execution, transitions state machine to `CANCELLED`, and emits `workflow.cancelled`.
- [x] **Mock mode purity:** Only harmless mock tools exist (`format_notes`, `schedule_reminder`); no external sending, network requests, or computer control.
- [x] **No duplicate schemas:** Reuses schemas defined once in contracts.
