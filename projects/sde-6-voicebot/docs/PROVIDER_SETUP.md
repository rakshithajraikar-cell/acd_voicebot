# Speech-to-Text Provider Setup Guide (W2)

**Workstream**: W2 — Speech-to-Text  
**Module**: `projects/sde-6-voicebot/src/providers/`  
**Standard**: Section 8 Engineering Standards (Zero Secrets Committed, Safe Defaults)

---

## 1. Architecture Overview

The Speech-to-Text subsystem uses a provider-neutral adapter architecture (`SpeechToTextAdapter`). This decouples downstream consumers (VAD, Reasoning, UI) from specific transcription vendors and enables seamless local development, deterministic CI testing, and production cloud deployment.

```
+──────────────────────────────────────────────────────────+
│             SpeechToTextAdapter Interface                │
├──────────────────────────────────────────────────────────┤
│  + initialize(): Promise<void>                           │
│  + transcribeChunk(chunk, options): Promise<Events[]>    │
│  + getHealth(): Promise<ProviderHealth>                  │
│  + cancel(): void                                        │
│  + reset(): void                                         │
+─────────────────────────────┬────────────────────────────+
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
+───────────────────────────+    +───────────────────────────+
│DeterministicFakeTranscriber│   │   Production Adapter      │
│(Default / Offline Mock)   │    │  (Whisper / Deepgram)     │
+───────────────────────────+    +───────────────────────────+
             ▲                                 │
             │   Failover on HTTP 429 / 503    │
             └─────────────────────────────────┘
```

---

## 2. Default: Mock Mode (Zero Configuration)

By default, the system operates in **Mock Mode** using `DeterministicFakeTranscriber`.

### Key Benefits:
- **Zero Credentials Required**: No API keys, accounts, or internet access required.
- **Deterministic & Bitwise Identical**: Outputs match fixture expectations across test runs.
- **Instant CI Execution**: Tests execute in milliseconds without external rate limits or billing.

### Quick Start:
```typescript
import { DeterministicFakeTranscriber, TranscriptionOrchestrator } from "sde-6-voicebot";

const transcriber = new DeterministicFakeTranscriber();
await transcriber.initialize();

const orchestrator = new TranscriptionOrchestrator({
  adapter: transcriber,
});
```

---

## 3. Real Provider Setup & Environment Configuration

To connect a live cloud transcription provider (e.g. OpenAI Whisper API, Deepgram, Google Cloud Speech-to-Text), set the following environment variables.

### Environment Variables Reference:

| Variable | Type | Default | Description |
|---|---|---|---|
| `STT_PROVIDER` | string | `mock` | Active provider: `mock`, `whisper`, `deepgram`, `google` |
| `STT_API_KEY` | string | *empty* | Provider authentication key (NEVER commit to git) |
| `STT_MODEL` | string | `whisper-1` | Model identifier (e.g. `nova-2`, `whisper-1`) |
| `STT_LANGUAGE` | string | `en-US` | Default BCP-47 language tag |
| `STT_ENDPOINT` | string | *provider default* | Custom endpoint URL or private VPC gateway |
| `STT_FALLBACK_TO_MOCK` | boolean | `true` | Automatically fall back to mock on 429/503 |
| `STT_TIMEOUT_MS` | number | `5000` | Per-chunk request deadline in milliseconds |
| `STT_MAX_RETRIES` | number | `3` | Maximum retry attempts with exponential backoff |

### Example Local `.env` (Excluded by `.gitignore`):
```bash
# Copy to .env.local (do NOT commit)
STT_PROVIDER=whisper
STT_API_KEY=sk-proj-example-placeholder-key
STT_MODEL=whisper-1
STT_FALLBACK_TO_MOCK=true
STT_TIMEOUT_MS=4000
```

---

## 4. Fallback & Resiliency Architecture

In production environments, external STT APIs can suffer from HTTP 429 (rate limiting / quota exhaustion) or transient HTTP 503 network drops.

The `FallbackSpeechToTextAdapter` wraps any primary provider with an automated mock failover:
1. If the primary provider succeeds, events flow normally.
2. If the primary provider hits quota exhaustion (429) or network disconnect (503):
   - The primary provider is marked degraded.
   - Failover automatically reroutes to `DeterministicFakeTranscriber`.
   - Audio is transcribed without dropped frames or pipeline crash.
   - A normalized `ErrorEnvelope` is emitted for telemetry without leaking credentials.

```typescript
import {
  FallbackSpeechToTextAdapter,
  DeterministicFakeTranscriber,
} from "sde-6-voicebot";

const fallbackAdapter = new FallbackSpeechToTextAdapter({
  primary: realProviderAdapter,
  fallback: new DeterministicFakeTranscriber(),
});
```

---

## 5. Security & Privacy Non-Negotiables

1. **Zero Secret Leaks**: Never check `.env`, secrets, or auth tokens into git.
2. **Redacted Logging**: All logs pass through `RedactedLogger`. Transcripts, audio buffers, and secrets are strictly sanitized before reaching log streams.
3. **No Raw Exceptions**: Errors are normalized into safe `ErrorEnvelope` payloads with redacted details.
