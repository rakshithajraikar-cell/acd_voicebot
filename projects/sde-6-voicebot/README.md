# Academiaai AI Voicebot — Team SDE 6

Welcome to the team project repository for **Academiaai AI Voicebot — Team SDE 6**.
All team work is organized by workstream within `projects/sde-6-voicebot/` following the shared engineering standards.

---

## Team Workstreams & Active Feature Branches

- **W1 — Audio & Voice Activity Detection (Weeks 1 & 2):** Rakshitha J Raikar (`feature/w1-audio-schemas`, `feature/w2-audio-lifecycle-vad`)
- **W3 — Context, Vision and Reasoning (Week 1 / Days 1–7):** Prathibhashree K (`feature/w3-context-schemas`)
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

## Workstream W3: Context and Reasoning Layer Architecture

This subsystem provides the typed schemas, privacy-preserving synthetic frame generation, versioned prompt management, deterministic mock reasoning, and strict validation engine.

Everything operates completely in **mock mode** with **zero paid API keys, zero external network calls, zero disk writes for frames, and zero real personal data**.

### Component Architecture
```
projects/sde-6-voicebot/
├── contracts/                        # Single source of truth for schemas & envelopes
│   ├── envelope.py                   # EventEnvelope, ErrorEnvelope, SessionState, WorkflowState
│   ├── context.py                    # ScreenContext, ContextItem, SourceReference, BoundingBox
│   └── reasoning.py                  # ReasoningRequest, ReasoningResult, ConfidenceLevel, ProviderStatus
├── src/voicebot/
│   ├── context/                      # Screen context capture & synthetic frame engine
│   │   ├── capture_adapter.py        # Privacy gatekeeper (Screen capture OFF by default, opt-in/opt-out)
│   │   └── synthetic_frames.py       # In-memory synthetic fixtures (Grades, Schedule, Library)
│   ├── prompts/                      # Prompt engineering & security quarantine
│   │   └── prompt_manager.py         # Versioned prompts (v1.0.0, v1.1.0) separating trusted/untrusted
│   ├── reasoning/                    # Deterministic mock reasoning engine
│   │   └── mock_reasoner.py          # Grounded reasoning, SourceReference citations, uncertainty surfacing
│   └── validation/                   # Schema validation & error reporting
│       └── validators.py             # Rejection of invalid inputs, format_error_envelope
├── tests/                            # Comprehensive Unit Tests covering normal, boundary & edge cases
│   ├── test_schemas.py
│   ├── test_synthetic_frames.py
│   ├── test_prompts.py
│   ├── test_mock_reasoning.py
│   └── test_validation.py
├── demo/                             # Day 7 Live Vertical Slice Demonstration
│   └── demo_grounded_response.py
└── README.md                         # Complete documentation & field specifications
```

---

## Typed Schema Specifications (W3)

Defined once inside `projects/sde-6-voicebot/contracts/` in accordance with Section 8 Engineering Standards:

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

### W3 Context & Reasoning Live Vertical Slice Demo:
```bash
python projects/sde-6-voicebot/demo/demo_grounded_response.py
```

### Running the Full Test Suite:
```bash
python -m unittest discover -s projects/sde-6-voicebot/tests -v
```

---

## Daily Progress Report Summary (Week 1 / Days 1–7)
- **Day 1–2**: Defined typed schemas (`ScreenContext`, `ContextItem`, `SourceReference`, `ReasoningRequest`, `ReasoningResult`, `EventEnvelope`, `ErrorEnvelope`) with full field documentation, units, constraints, and immutability.
- **Day 3–4**: Implemented `ScreenCaptureAdapter` (OFF by default, opt-in/opt-out), `SyntheticFrameGenerator` (four fixtures: grades, schedule, loans, blank), `PromptManager` (versioned v1.0.0 and v1.1.0 with strict isolation and injection defense), and deterministic `MockReasoningEngine`.
- **Day 5–6**: Built comprehensive `validators.py` and unit test suite with 30 tests covering valid, boundary, invalid, and edge cases. 100% pass rate.
- **Day 7**: Created Day 7 live demo script `demo_grounded_response.py`, verified all acceptance criteria, and opened PR #4 into `team/sde-6-voicebot`.
