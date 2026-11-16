# Academiaai AI Voicebot — SDE 6 (W2: Speech-to-Text)

**Workstream**: W2 — Speech-to-Text  
**Assigned Student**: Pavithra P (SDE 6, Member 2)  
**Milestones Delivered**: 
- **Week 1 (Days 1–7)**: Transcript Schemas, Fake Transcriber & Segment Accumulator
- **Week 2 (Days 8–14)**: Orchestration, Ordering & De-duplication, Retries & Preprocessing
- **Week 3 (Days 15–21)**: Revisions & Finalization, Mock Fallback & Event-Stream Integration  
**Team Branch**: `team/sde-6-voicebot`  
**Feature Branch**: `feature/w2-speech-to-text`  
**Base Repository**: [https://github.com/Yashuudevang/acd_voicebot](https://github.com/Yashuudevang/acd_voicebot)

---

## 1. Overview & Architectural Boundaries

This module forms the foundation of the Speech-to-Text (STT) pipeline for SDE 6. It operates strictly in **Mock Mode by default**, requiring zero paid external API keys or credentials.

### Key Capabilities Delivered:

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

---

## 2. Directory Structure

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

---

## 3. How to Run

### Install Dependencies
```powershell
cd projects/sde-6-voicebot
npm install
```

### Typecheck (Zero Errors)
```powershell
npm run typecheck
```

### Run All 53 Tests
```powershell
npm run test
```

### Run Live Demos
- **Week 1**: `npm run demo`
- **Week 2**: `npm run demo:week2`
- **Week 3**: `npm run demo:week3`

---

## 4. Acceptance Checklist

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

## 5. Daily Progress Report (Week 3: Days 15–21)

- **Day 15–16 (Revisions & Confidence Thresholds)**:
  - Added support for `transcript.revised` events to update transcript segments in-place.
  - Implemented confidence threshold filtering and uncertainty marking (`[uncertain: ...]`).
  - Enforced strict session isolation rejecting foreign session IDs with `SESSION_MISMATCH`.
- **Day 17–18 (Mock Fallback & Cancellation)**:
  - Created `FallbackSpeechToTextAdapter` with automated failover on HTTP 429 quota exhaustion and network disconnects.
  - Implemented cooperative cancellation propagating through primary and fallback providers.
- **Day 19–20 (W1 Audio Gateway & W5 Backend Stream Integration)**:
  - Created `AudioEventGateway` with sequence continuity tracking and missing-chunk gap detection.
  - Created `BackendEventStreamBridge` with chronological event caching and replay/reconnection capabilities.
- **Day 21 (Integration Demo & Gate Approval)**:
  - Added 11 new integration tests (total 53 tests passing).
  - Built and verified `src/demo/week3-integration-demo.ts` live CLI demonstration.
