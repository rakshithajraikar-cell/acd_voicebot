# Academiaai AI Voicebot — Team SDE 6

Welcome to the team project repository for **Academiaai AI Voicebot — Team SDE 6**.
All team work is organized by workstream within `projects/sde-6-voicebot/` following the shared engineering standards.

---

## Team Workstreams & Active Feature Branches

- **W1 — Audio & Voice Activity Detection (Weeks 1 & 2):** Rakshitha J Raikar (`feature/w1-audio-schemas`, `feature/w2-audio-lifecycle-vad`)
- **W3 — Context, Vision and Reasoning (Weeks 1 & 2 / Days 1–14):** Prathibhashree K (`feature/w3-context-schemas`, `feature/w3-context-builder-llm-adapter`)
- **Target Team Branch:** `team/sde-6-voicebot`

---

## Workstream W1: Audio & VAD Architecture

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

## Workstream W3: Context, Vision and Reasoning Architecture (Weeks 1 & 2)

This subsystem provides the typed schemas, privacy-preserving synthetic frame generation, opt-in capture adapter with sampling and size limits, Vision/OCR extraction interface, bounded context builder with recency/relevance ranking, versioned prompt management, deterministic mock reasoning, and an LLM client adapter with timeout, bounded retries, and schema/safety validation.

Everything operates completely in **mock mode** with **zero paid API keys, zero external network calls, zero disk writes for frames, and zero real personal data**.

### W3 Context & Reasoning Architecture Diagram

```
+-----------------------------------------------------------------------------------------------------+
|                               W3 CONTEXT & REASONING ARCHITECTURE                                   |
|                                                                                                     |
|  [SyntheticFrameGenerator]                                                                          |
|   - In-memory synthetic fixtures (Grades, Schedule, Library)                                        |
|   - Pure mock data: Zero real screenshots, Zero PII, Zero disk writes                               |
|           │                                                                                         |
|           ▼                                                                                         |
|  [ScreenCaptureAdapter (Opt-In Gatekeeper)]                                                         |
|   - Capture OFF by default; requires explicit opt-in consent                                        |
|   - Immediate purging upon consent withdrawal                                                       |
|   - Sampling Limits: Rate throttling / minimum capture intervals (cache/reject policy)              |
|   - Size Limits: Max dimension clamping (1920x1080) and payload byte boundaries                     |
|           │                                                                                         |
|           ▼                                                                                         |
|  [VisionAdapterInterface & MockVisionOCRAdapter]                                                    |
|   - Abstract vision contract with deterministic mock implementation                                 |
|   - Extracts structured text, confidence scores, and layout BoundingBoxes                           |
|   - Returns empty results when capture is disabled (Privacy preservation)                           |
|           │                                                                                         |
|           ▼                                                                                         |
|  [BoundedContextBuilder]                                                                            |
|   - Stale filtering: Automatic eviction of items exceeding TTL                                     |
|   - Token budget approximation: Character and structural overhead estimation                        |
|   - Multi-factor ranking: Balances query relevance (keyword/phrase match) and item recency          |
|   - Strict token budget bounding: Pack context items safely into prompt window                      |
|           │                                                                                         |
|           ▼                                                                                         |
|  [LLMClientAdapter]                                                                                 |
|   - Defaults to MockLLMBackend (Zero API keys, offline deterministic generation)                    |
|   - Timeout enforcement: Configurable per-attempt deadline                                         |
|   - Bounded retries: Exponential backoff for transient errors                                       |
|   - Structured output validation: Strict schema validation into ReasoningResult                     |
|   - Malformed output rejection: Catches bad JSON, missing fields, out-of-range confidence           |
|   - Unsafe output rejection: Detects prompt injections, script tags, dangerous commands             |
|   - Error translation: Standard ErrorEnvelope mappings                                              |
+-----------------------------------------------------------------------------------------------------+
```

### Component Structure
```
projects/sde-6-voicebot/
├── contracts/                        # Single source of truth for schemas & envelopes
│   ├── envelope.py                   # EventEnvelope, ErrorEnvelope, SessionState, WorkflowState
│   ├── context.py                    # ScreenContext, ContextItem, SourceReference, BoundingBox
│   └── reasoning.py                  # ReasoningRequest, ReasoningResult, ConfidenceLevel, ProviderStatus
├── src/voicebot/
│   ├── context/                      # Screen context capture & synthetic frame engine
│   │   ├── capture_adapter.py        # Privacy gatekeeper (Screen capture OFF by default, sampling/size limits)
│   │   ├── synthetic_frames.py       # In-memory synthetic fixtures (Grades, Schedule, Library)
│   │   ├── vision_adapter.py         # VisionAdapterInterface & MockVisionOCRAdapter
│   │   └── context_builder.py        # BoundedContextBuilder (token budget, relevance/recency, stale pruning)
│   ├── prompts/                      # Prompt engineering & security quarantine
│   │   └── prompt_manager.py         # Versioned prompts (v1.0.0, v1.1.0) separating trusted/untrusted
│   ├── reasoning/                    # Deterministic mock reasoning & LLM client adapter
│   │   ├── mock_reasoner.py          # Grounded reasoning, SourceReference citations, uncertainty surfacing
│   │   └── llm_adapter.py            # LLMClientAdapter with timeout, bounded retries & schema/safety validation
│   └── validation/                   # Schema validation & error reporting
│       └── validators.py             # Rejection of invalid inputs, format_error_envelope
├── tests/                            # Comprehensive Unit Tests covering normal, boundary & edge cases
│   ├── test_schemas.py
│   ├── test_synthetic_frames.py
│   ├── test_prompts.py
│   ├── test_mock_reasoning.py
│   ├── test_validation.py
│   ├── test_capture_sampling_and_limits.py   # Week 2 capture limits & sampling tests
│   ├── test_vision_adapter.py               # Week 2 vision & OCR adapter tests
│   ├── test_context_builder.py              # Week 2 bounded context builder tests
│   ├── test_llm_adapter.py                  # Week 2 LLM timeout, retry & malformed/unsafe output tests
│   └── test_week2_end_to_end.py             # Week 2 integrated vertical slice pipeline tests
├── demo/                             # Live Vertical Slice Demonstrations
│   ├── demo_grounded_response.py            # Week 1 Live Demonstration
│   └── demo_context_reasoning_week2.py      # Week 2 Live Demonstration
└── README.md                         # Complete documentation & specifications
```

---

## Typed Schema Specifications (W3)

Defined once inside `projects/sde-6-voicebot/contracts/` in accordance with Section 8 Engineering Standards (reused across Weeks 1 & 2 without duplication):

### ScreenContext (`contracts/context.py`)
- `context_id`: UUID v4 string
- `session_id`: Session UUID string
- `timestamp`: ISO 8601 UTC string
- `capture_enabled`: Boolean (**Default: False**)
- `capture_allowed_by_user`: Boolean (**Default: False**, opt-in consent)
- `window_title`: Optional synthetic window title
- `application_name`: Optional synthetic application name
- `screen_width`: Pixels (`> 0`, default 1920)
- `screen_height`: Pixels (`> 0`, default 1080)
- `ocr_text`: Extracted text from synthetic frame
- `bounding_boxes`: List of UI `BoundingBox` elements
- `is_synthetic`: Boolean (**Must be True**)

### ContextItem (`contracts/context.py`)
- `item_id`: UUID v4 string
- `item_type`: `ContextItemType` enum (`screen_frame`, `ocr_text`, etc.)
- `content`: Textual observation or extracted text
- `source`: `SourceReference` citation object
- `confidence`: Score ratio `[0.0 - 1.0]`
- `created_at`: ISO 8601 UTC timestamp
- `ttl_seconds`: Expiration seconds for stale context
- `is_synthetic`: Boolean (**Must be True**)

### SourceReference (`contracts/context.py`)
- `source_id`: Unique citation identifier string
- `source_type`: `SourceType` enum (`synthetic_screen`, `mock_document`, etc.)
- `uri`: Synthetic resource locator (e.g. `synthetic://screen/frame_001`)
- `title`: Human-readable source title
- `snippet`: Extracted excerpt supporting the claim
- `timestamp`: ISO 8601 UTC date

### ReasoningRequest & ReasoningResult (`contracts/reasoning.py`)
- `ReasoningRequest`: `request_id`, `session_id`, `correlation_id`, `user_query`, `context_items`, `prompt_version`, `temperature=0.0`, `max_tokens=1024`, `mock_mode=True`.
- `ReasoningResult`: `result_id`, `request_id`, `session_id`, `correlation_id`, `response_text`, `sources_used`, `confidence`, `confidence_level`, `has_sufficient_evidence`, `uncertainty_reason`, `suggested_action`, `execution_time_ms`, `is_mock=True`.

---

## Running Demonstrations & Test Suites

### W1 & W2 Audio Pipeline Demonstrations:
```bash
# Week 1 CLI Stream Demo
python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --count 10

# Week 2 Audio Pipeline & VAD Demo
python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py
```

### W3 Context & Reasoning Live Vertical Slice Demonstrations:
```bash
# Week 1 Live Grounded Reasoning Slice
python projects/sde-6-voicebot/demo/demo_grounded_response.py

# Week 2 Live Context, Vision, Token Budget & LLM Adapter Demonstration
python projects/sde-6-voicebot/demo/demo_context_reasoning_week2.py
```

### Running the Full Test Suite:
```bash
# Using pytest (all 116 tests across W1 & W3)
python -m pytest projects/sde-6-voicebot/tests -v

# Using Python unittest discovery
python -m unittest discover -s projects/sde-6-voicebot/tests -v
```

---

## Daily Progress Report Summary

### Week 1 (Days 1–7)
- **Day 1–2**: Defined typed schemas (`ScreenContext`, `ContextItem`, `SourceReference`, `ReasoningRequest`, `ReasoningResult`, `EventEnvelope`, `ErrorEnvelope`) with full field documentation, units, constraints, and immutability.
- **Day 3–4**: Implemented `ScreenCaptureAdapter` (OFF by default, opt-in/opt-out), `SyntheticFrameGenerator` (four fixtures: grades, schedule, loans, blank), `PromptManager` (versioned v1.0.0 and v1.1.0 with strict isolation and injection defense), and deterministic `MockReasoningEngine`.
- **Day 5–6**: Built comprehensive `validators.py` and unit test suite with 30 tests covering valid, boundary, invalid, and edge cases. 100% pass rate.
- **Day 7**: Created Day 7 live demo script `demo_grounded_response.py`, verified all acceptance criteria, and opened PR #4 into `team/sde-6-voicebot`.

### Week 2 (Days 8–14)
- **Day 8–9**: Enhanced `ScreenCaptureAdapter` with sampling rate limits (`min_interval_seconds`, `throttle_policy="cache"|"reject"`) and frame size limits (`max_width`, `max_height`, `max_payload_bytes`). Designed `VisionAdapterInterface` and implemented `MockVisionOCRAdapter` providing offline deterministic OCR text and UI bounding box extraction.
- **Day 10–11**: Developed `BoundedContextBuilder` with stale filtering using item TTL and timestamps, token-budget approximation, multi-factor scoring (relevance weight + recency weight), and strict budget packing.
- **Day 12–13**: Created `LLMClientAdapter` supporting offline mock operation by default, per-request timeout enforcement, bounded retries with exponential backoff, and strict schema validation of structured outputs.
- **Day 14**: Built security and safety guardrails detecting and rejecting malformed outputs (`MalformedOutputError`) and unsafe model responses (`UnsafeOutputError`). Developed `demo_context_reasoning_week2.py`, expanded test suite to 116 tests with 100% pass rate, and prepared Week 2 pull request into `team/sde-6-voicebot`.
