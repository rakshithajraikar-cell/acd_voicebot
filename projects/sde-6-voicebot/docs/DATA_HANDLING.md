# Academiaai Voicebot — Data Handling & Retention Policy (W3)

**Workstream**: W3 – Context, Vision & Reasoning  
**Team**: SDE 6  
**Author**: Prathibhashree K  
**Version**: 1.0.0 (Release Hardening / Day 30)

---

## 1. Executive Summary & Privacy Principles

Academiaai Voicebot is built upon strict privacy-by-design engineering principles. The Context & Reasoning subsystem operates in **Mock Mode by default**, completely isolated from paid external APIs, cloud data brokers, or unmonitored telemetry.

Non-Negotiable Guarantees:
1. **Screen Capture is OFF by default** (`capture_enabled=False`, `capture_allowed_by_user=False`).
2. **Explicit Opt-In Required**: Capture only begins when the user triggers an explicit opt-in action.
3. **Immediate Consent Revocation**: When consent is withdrawn, capture halts immediately, and all retained frames and observations are purged from memory.
4. **Zero Real Screen Capture in CI/Tests**: Only verified synthetic mock fixtures are processed; no real OS screenshots or desktop recordings are captured or persisted.
5. **No Disk Persistence by Default**: All visual frames and observations exist solely in volatile RAM during active sessions.

---

## 2. What is Captured?

When a user explicitly opts in, the capture adapter gathers only synthetic visual context:

| Data Field | Description | Sensitivity | Permissible Values / Constraints |
| :--- | :--- | :--- | :--- |
| `context_id` | UUID v4 frame identifier | Non-sensitive | Standard UUID v4 |
| `session_id` | Active voicebot session identifier | Operational | Linked to active session only |
| `timestamp` | ISO 8601 UTC creation time | Operational | E.g. `2026-11-24T12:00:00Z` |
| `is_synthetic` | Mock pipeline origin flag | Compliance | **Always `True`** |
| `window_title` | Active application title | Low | Synthetic string (e.g. "Student Portal") |
| `application_name` | Name of foreground application | Low | E.g. "MockBrowser", "MockCalendar" |
| `screen_width` / `height` | Frame dimensions in pixels | Technical | Maximum clamped to 1920x1080 |
| `ocr_text` | Extracted visual text | Medium | Subject to automatic PII redaction |
| `bounding_boxes` | UI element bounding coordinates | Low | `(x, y, width, height, label)` |

---

## 3. What is Processed?

All captured context undergoes automated sanitization and bounded filtering:

1. **Automated PII & Credential Redaction**:
   - `TextRedactor` intercepts all text before it enters the context builder, prompts, or logs.
   - Email addresses are masked with `[EMAIL_REDACTED]`.
   - API keys and tokens (e.g., `ghp_...`, Bearer JWTs, secret keys) are masked with `[API_TOKEN_REDACTED]`.
   - Phone numbers and national identifiers (SSNs) are masked with `[PHONE_REDACTED]` and `[SSN_REDACTED]`.

2. **Perceptual Deduplication**:
   - Consecutive frames are fingerprinted using a SHA-256 digest of window titles, OCR content, and sorted bounding box coordinates.
   - Duplicate frames within the deduplication window (default 10.0 seconds) are dropped immediately.

3. **Token Budgeting & Stale Pruning**:
   - Context items are scored based on recency and relevance to the user's specific query.
   - Items exceeding the time-to-live (TTL) threshold are discarded.
   - Items are packed into the token budget (default 1024 tokens) to avoid overwhelming the LLM context window.

4. **Prompt Injection Scanning**:
   - Scanned against 16+ adversarial injection patterns (instruction overrides, developer mode triggers, delimiter breaking).
   - Injections are neutralized, logged to audit telemetry, and refused without executing the malicious directive.

---

## 4. What is Retained, and for How Long?

### Volatile Memory Only
All screen context items, synthetic frames, and visual observations are retained **strictly in volatile system memory (RAM)**.
- **Zero Disk Writes**: No image files, OCR dumps, or raw transcripts are saved to permanent local storage or databases.
- **No Remote Telemetry**: No visual or textual payloads are transmitted to external servers.

### Retention Lifecycle Matrix

| Event / Boundary | Retention Action | Maximum Duration |
| :--- | :--- | :--- |
| **Normal Active Session** | Ingested in bounded ring buffer | `ttl_seconds` (default: 300 seconds / 5 minutes) |
| **Stale Pruning Interval** | Evaluated on every prompt build | Items > 300s old are deleted immediately |
| **User Consent Withdrawal** | **Immediate hard purge** | **0 seconds** (All observations & frames purged) |
| **Session Stop / Expiry** | Session lifecycle controller terminates buffer | Immediate garbage collection on session teardown |
| **Application Shutdown** | OS terminates process | 0 bytes retained on disk |

---

## 5. Security & Audit Fences

1. **Trusted vs Untrusted Quarantine**:
   - Screen context is framed inside `<untrusted_context>` XML tags with delimiter sanitization (`<` and `>` encoded as entities).
2. **Workflow Proposal Gate**:
   - The reasoning engine only generates draft proposals (`WorkflowProposal`). Consequential tools (email sending, grade modification) require explicit downstream user approval before any tool execution occurs.
3. **Audit Trail**:
   - All state transitions (Consent Granted, Consent Revoked, Injections Blocked, Stale Drops, Duplicate Drops) are recorded with timestamp and correlation ID in redacted logs.

---

## 6. Per-Stage Latency Instrumentation & Benchmarks

The Context & Reasoning pipeline is instrumented with granular stopwatch tracking across every execution stage (`LatencyTracker` and `LatencyReport`).

### Measured Per-Stage Latency (Release Benchmark)

| Stage | Instrumented Operation | Duration (ms) | Notes |
| :--- | :--- | :---: | :--- |
| **Stage 1: Capture** | Screen capture adapter opt-in check & dimension clamping | `0.097 ms` | Strict sampling & dimension bounding |
| **Stage 2: OCR & Vision** | Visual OCR text & layout bounding box extraction | `4.375 ms` | Deterministic synthetic extraction |
| **Stage 3: Context Building** | Recency/relevance scoring & token-budget packing | `0.424 ms` | Multi-factor prioritization within 1024 tokens |
| **Stage 4: Prompt Rendering** | Injection scanning, PII redaction & XML quarantine | `0.726 ms` | Dual-vector sanitization (query + screen) |
| **Stage 5: Inference Execution** | Deterministic mock reasoning inference | `0.648 ms` | Evidence grounding & uncertainty resolution |
| **Stage 6: Output Validation** | Structured schema and safety contract validation | `0.013 ms` | Output validation against `ReasoningResult` |
| **Total End-to-End Latency** | **Full pipeline execution** | **`7.659 ms`** | **Sub-10ms response time** |

### Command to Reproduce Latency Measurements

To execute the live latency instrumentation benchmark and print the full breakdown:
```bash
python projects/sde-6-voicebot/demo/demo_release_hardening.py
```

To run the automated latency test suite:
```bash
python -m unittest discover -s projects/sde-6-voicebot/tests -p "test_latency_instrumentation.py"
```

