# Academiaai AI Voicebot — Team SDE 6

Welcome to the team project repository for **Academiaai AI Voicebot — Team SDE 6**.
All team work is organized by workstream within `projects/sde-6-voicebot/` following the shared Section 8 engineering standards.

---

## Team Workstreams & Active Feature Branches

- **W1 — Audio & Voice Activity Detection (Weeks 1 & 2):** Rakshitha J Raikar (`feature/w1-audio-schemas`, `feature/w2-audio-lifecycle-vad`)
- **W2 — Speech-to-Text (Weeks 1, 2 & 3):** Pavithra P (`feature/w2-speech-to-text`)
- **W3 — Context, Vision and Reasoning (Week 1 / Days 1–7):** Prathibhashree K (`feature/w3-context-schemas`)
- **Target Team Branch:** `team/sde-6-voicebot`
- **Base Repository:** [https://github.com/Yashuudevang/acd_voicebot](https://github.com/Yashuudevang/acd_voicebot)

---

## 1. Workstream W1: Audio & VAD Architecture

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

## 2. Workstream W2: Speech-to-Text Subsystem

**Assigned Student**: Pavithra P (SDE 6, Member 2)  
**Feature Branch**: `feature/w2-speech-to-text`  
**Milestones Delivered**:
- **Week 1 (Days 1–7)**: Transcript Schemas, Fake Transcriber & Segment Accumulator
- **Week 2 (Days 8–14)**: Orchestration, Resampling, Normalization & Bounded Retries
- **Week 3 (Days 15–21)**: Revisions & Finalization, Mock Fallback & Event-Stream Integration

### Architectural Capabilities Delivered:

#### Week 1 (Foundation & Schemas)
1. **Contract Definition (`src/contracts/`)**:
   - `TranscriptSegment` and `TranscriptEvent` schemas strictly typed with runtime Zod validation.
   - Unified `EventEnvelope` (`event_id`, `event_type`, `schema_version`, `session_id`, `correlation_id`, `timestamp`, `producer`, `payload`).
   - Standard `ErrorEnvelope` (`code`, `message_safe_for_user`, `retryable`, `correlation_id`, `details_redacted`).
   - Defined once inside `projects/sde-6-voicebot/` to prevent duplicate schema sprawl.

2. **Provider-Neutral Adapter & Fake Transcriber (`src/providers/`)**:
   - `SpeechToTextAdapter` decoupled interface.
   - `DeterministicFakeTranscriber`: Bitwise-identical output on repeated runs without external API keys.

3. **Ordered Segment Accumulator (`src/accumulator/`)**:
   - Chronological sorting by `sequence_number` and `start_time_ms`.
   - Out-of-order reconciliation and duplicate suppression.
   - Interim-to-final replacement lifecycle.

#### Week 2 (Core Implementation & Orchestration)
4. **Audio Preprocessor (`src/preprocessing/`)**:
   - Resampling: Converts 8000Hz, 44100Hz, and 48000Hz audio to standardized 16000Hz.
   - Amplitude Normalization: Scales audio to optimal target peak (0.95) and eliminates clipping.
   - DC Offset Removal: Subtracts signal bias.
   - Stereo to Mono Downmixing: Averages 2-channel audio into a clean single channel.

5. **Resilience, Timeout & Bounded Retries (`src/resilience/`)**:
   - `RetryHandler`: Configurable `maxRetries`, `timeoutMs`, and exponential backoff with jitter.
   - Safe error normalization: Maps all exceptions into user-safe `ErrorEnvelope`s without leaking stack traces or credentials.

6. **Transcription Orchestrator (`src/orchestrator/`)**:
   - Connects: Audio Chunk (W1) ➔ Preprocessing ➔ Timeout/Retry Layer ➔ Provider Adapter ➔ Segment Accumulator.
   - Chunk-level duplicate suppression.
   - Live stream event broadcasting (`transcript.interim`, `transcript.final`, `transcript.error`).
   - Observability metrics tracking (chunks received, duplicates suppressed, retries, errors).

#### Week 3 (Workflow & Integration)
7. **Revisions & Confidence Thresholding (`src/accumulator/segment-accumulator.ts`)**:
   - `transcript.revised` handling: In-place revision of segments as acoustic context clarifies earlier words.
   - Configurable confidence threshold (e.g., 0.70) tagging low-confidence speech with uncertainty markers (`[uncertain: ...]`).
   - Strict session isolation: Rejects foreign session events with `SESSION_MISMATCH`.

8. **Provider Fallback & Cancellation (`src/providers/fallback-provider.ts`)**:
   - `FallbackSpeechToTextAdapter`: Automatically falls back to mock provider upon primary quota exhaustion (HTTP 429), network drops, or timeouts.
   - Cancellation: Cleanly stops in-flight transcriptions across all active providers.
   - Dual-failure safety: Safely normalizes failures without throwing unhandled exceptions.

9. **W1 Audio Gateway & W5 Backend Event Bridge (`src/integration/stream-bridge.ts`)**:
   - `AudioEventGateway`: Sequence continuity tracking and missing-chunk gap detection.
   - `BackendEventStreamBridge`: Reconnect & replay buffer (`replayEvents(sessionId, afterEventId)`) ensuring zero event loss across UI/backend drops.

### Directory Structure (W2 TypeScript Pipeline):
```
projects/sde-6-voicebot/
├── README.md                      # Complete module documentation & PR evidence
├── package.json                   # Dependencies: Zod; Dev: TypeScript, Vitest, tsx
├── tsconfig.json                  # Strict TypeScript configuration (ES2022)
├── vitest.config.ts               # Test suite configuration
├── .gitignore                     # Git ignore rules (no secrets, recordings, or node_modules)
├── src/
│   ├── contracts/
│   │   ├── common.ts              # EventEnvelope, ErrorEnvelope, Session & Workflow state enums
│   │   ├── transcript.ts          # TranscriptSegment, TranscriptEvent, AudioChunk schemas & validators
│   │   └── index.ts
│   ├── providers/
│   │   ├── stt-adapter.ts         # Provider-neutral SpeechToTextAdapter interface
│   │   ├── fake-transcriber.ts    # Deterministic mock transcriber implementation
│   │   ├── fallback-provider.ts   # Failover fallback adapter for quota/network errors
│   │   └── index.ts
│   ├── accumulator/
│   │   ├── segment-accumulator.ts # Ordered segment accumulator, revisions & confidence thresholds
│   │   └── index.ts
│   ├── preprocessing/
│   │   ├── audio-preprocessor.ts  # Resampling (48k/8k -> 16k), Normalization, Downmixing
│   │   └── index.ts
│   ├── resilience/
│   │   ├── retry-handler.ts       # Bounded retries, timeouts, and error normalizer
│   │   └── index.ts
│   ├── orchestrator/
│   │   ├── transcription-orchestrator.ts # Core pipeline coordinator & metrics
│   │   └── index.ts
│   ├── integration/
│   │   ├── stream-bridge.ts       # W1 Audio Gateway, gap detection & W5 Backend Event Stream Bridge
│   │   └── index.ts
│   ├── fixtures/
│   │   └── transcript-fixtures.ts # Repeatable synthetic audio and edge case fixtures
│   ├── demo/
│   │   ├── chunk-to-transcript.ts       # Week 1 live demo
│   │   ├── week2-orchestrator-demo.ts   # Week 2 live demo
│   │   └── week3-integration-demo.ts    # Week 3 live demo
│   └── index.ts                   # Unified library entry point
└── tests/
    ├── contracts/
    │   └── transcript-schemas.test.ts        # 12 tests: schema validation, boundaries, invalid rejection
    ├── providers/
    │   ├── fake-transcriber.test.ts          # 9 tests: determinism, interim/final emission, cancellation
    │   └── fallback-provider.test.ts         # 5 tests: primary success, quota 429 fallback, network 503 fallback
    ├── accumulator/
    │   └── segment-accumulator.test.ts       # 8 tests: ordering, duplicate suppression, session boundary
    ├── preprocessing/
    │   └── audio-preprocessor.test.ts        # 5 tests: resampling (48k/8k), normalization, stereo downmix
    ├── resilience/
    │   └── retry-handler.test.ts             # 4 tests: timeouts, bounded retries, error normalization
    ├── orchestrator/
    │   └── transcription-orchestrator.test.ts# 4 tests: end-to-end orchestration, duplicates, errors
    └── integration/
        ├── revision-confidence.test.ts       # 3 tests: transcript.revised, confidence filtering, session mismatch
        └── audio-gateway.test.ts             # 3 tests: W1 chunk routing, sequence gap detection, W5 event replay
```

### Acceptance Checklist (W2):

| # | Acceptance Criteria | Status | Evidence / Location |
|---|---|:---:|---|
| 1 | Interim results revised & finalized with clear events | Passed | `src/accumulator/segment-accumulator.ts` |
| 2 | Every transcript event carries session ID | Passed | Validated in `TranscriptEventSchema` & `EventEnvelope` |
| 3 | Low-confidence segments handled by threshold | Passed | `tests/integration/revision-confidence.test.ts` |
| 4 | Cancellation stops in-flight transcription cleanly | Passed | `src/providers/fallback-provider.ts` |
| 5 | Quota & network failures fall back to mock provider | Passed | `tests/providers/fallback-provider.test.ts` |
| 6 | Audio events flow into transcription end-to-end | Passed | `tests/integration/audio-gateway.test.ts` |
| 7 | Transcript events reach backend event stream with replay | Passed | `src/integration/stream-bridge.ts` |
| 8 | Missing chunks & out-of-order chunks handled | Passed | `tests/integration/audio-gateway.test.ts` |
| 9 | 100% test pass rate across all suites | Passed | **53/53 tests passing** |

---

## 3. Workstream W3: Context and Reasoning Layer Architecture

This subsystem provides the typed schemas, privacy-preserving synthetic frame generation, versioned prompt management, deterministic mock reasoning, and strict validation engine.

Everything operates completely in **mock mode** with **zero paid API keys, zero external network calls, zero disk writes for frames, and zero real personal data**.

### Component Architecture (W3 Python Pipeline)
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

## 4. How to Run & Verify

### Workstream W2 (Speech-to-Text - TypeScript):

```powershell
cd projects/sde-6-voicebot

# Install dependencies
npm install

# Typecheck (0 errors)
npm run typecheck

# Run Vitest test suite (53/53 tests pass)
npm run test

# Run Live Demos
npm run demo          # Week 1 Live Demo
npm run demo:week2    # Week 2 Orchestrator Demo
npm run demo:week3    # Week 3 Integration Demo
```

### Workstream W1 & W3 (Audio & Reasoning - Python):

```powershell
# Week 1 CLI Stream Demo
python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --count 10

# Week 2 Audio Pipeline & VAD Demo
python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py

# W3 Context & Reasoning Live Vertical Slice Demo
python projects/sde-6-voicebot/demo/demo_grounded_response.py

# Run Python Unit Tests
python -m unittest discover -s projects/sde-6-voicebot/tests -v
```

---

## 5. Daily Progress Reports

### Workstream W2 (Speech-to-Text — Pavithra P)
- **Week 1 (Days 1–7: Schemas & Mock Transcriber)**:
  - Day 1–2: Defined typed Zod schemas (`TranscriptSegment`, `TranscriptEvent`, `EventEnvelope`, `ErrorEnvelope`) with immutability and runtime validation.
  - Day 3–4: Implemented `DeterministicFakeTranscriber` emitting predictable interim and final segments across deterministic mock waveforms.
  - Day 5–6: Built `SegmentAccumulator` managing monotonic ordering, duplicate rejection, and interim-to-final replacement.
  - Day 7: Created Week 1 CLI demo and verification suite.
- **Week 2 (Days 8–14: Orchestration & Resilience)**:
  - Day 8–9: Implemented `AudioPreprocessor` supporting 8kHz/44.1kHz/48kHz to 16kHz resampling, peak amplitude normalization, DC offset removal, and stereo-to-mono downmixing.
  - Day 10–11: Implemented `RetryHandler` with bounded retries, exponential backoff, deadline timeouts, and user-safe error normalization.
  - Day 12–13: Implemented `TranscriptionOrchestrator` linking audio ingestion, preprocessing, retries, mock transcription, and accumulator with duplicate suppression and metrics.
  - Day 14: Created Week 2 CLI demo and test suite (total 42 tests passing).
- **Week 3 (Days 15–21: Revisions, Fallback & Event Streams)**:
  - Day 15–16: Added `transcript.revised` in-place segment revisions, confidence thresholding (`0.70`), and strict session isolation.
  - Day 17–18: Implemented `FallbackSpeechToTextAdapter` with automated fallback on quota exhaustion (HTTP 429) or network drop, and cooperative cancellation.
  - Day 19–20: Connected `AudioEventGateway` (W1 event routing & missing-chunk gap detection) and `BackendEventStreamBridge` (W5 backend event transport with reconnect buffer and replay).
  - Day 21: Added 11 integration tests (total 53 tests passing), created Week 3 live integration demo, and updated team integration evidence.

### Workstream W3 (Context & Reasoning — Prathibhashree K)
- **Week 1 (Days 1–7)**:
  - Day 1–2: Defined typed schemas (`ScreenContext`, `ContextItem`, `SourceReference`, `ReasoningRequest`, `ReasoningResult`, `EventEnvelope`, `ErrorEnvelope`).
  - Day 3–4: Implemented `ScreenCaptureAdapter`, `SyntheticFrameGenerator`, `PromptManager`, and `MockReasoningEngine`.
  - Day 5–6: Built `validators.py` and unit test suite with 30 tests. 100% pass rate.
  - Day 7: Created live demo script `demo_grounded_response.py` and opened PR #4.
