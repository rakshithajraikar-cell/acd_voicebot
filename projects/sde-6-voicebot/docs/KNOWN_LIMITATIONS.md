# Known Limitations & Edge Cases (W2: Speech-to-Text)

**Workstream**: W2 — Speech-to-Text  
**Module**: `projects/sde-6-voicebot/`  
**Current Milestone**: Week 4 Hardening (Release Gate Day 30)

---

## 1. Audio Encoding & Format Constraints

- **Supported Inputs**: Raw linear PCM data represented as `Uint8Array` (16-bit signed PCM byte representation) or `Float32Array` normalized between `[-1.0, 1.0]`.
- **Supported Sample Rates**: Native resampling handles `8000 Hz`, `16000 Hz`, `44100 Hz`, and `48000 Hz` automatically downsampled or upsampled to the standardized `16000 Hz` model baseline.
- **Limitation**: Highly compressed containers (e.g. `.mp3`, `.ogg`, `.webm`, `.mp4`) must have their container packaging demuxed into linear PCM audio frames before ingestion into `AudioPreprocessor`.
- **Channels**: Multi-channel (stereo) audio is downmixed to single-channel (mono) by averaging channels. Directional spatial audio cues are flattened.

---

## 2. Segment Accumulation & Memory Footprint

- **In-Memory Retention**: The `SegmentAccumulator` retains all finalized and interim segments in-memory for the duration of an active session to support out-of-order reassembly and in-place revisions.
- **Scaling Recommendation**: For continuous multi-hour sessions (> 4 hours), client applications should periodically call `orchestrator.reset()` at conversational boundaries or persist archived segments to backend storage (W5).

---

## 3. Natural Language & Model Coverage

- **Default Locale**: Default mock transcriber models and synthetic fixtures simulate `en-US` conversational speech.
- **Multilingual Support**: Switching to non-English languages requires configuring a live cloud STT provider (e.g. `STT_LANGUAGE=es-ES`) supporting target BCP-47 language codes.
- **Confidence Scoring**: Mock mode generates synthetic confidence scores in range `[0.75, 0.99]`. Real providers may produce lower confidence on noisy or overlapping background speech.

---

## 4. Cancellation & Concurrency Semantics

- **Mid-Stream Cancellation**: Calling `orchestrator.cancel(sessionId)` immediately ceases downstream emissions and flags the session as cancelled. Chunks already processed and committed to the accumulator remain intact; pending or future chunks are rejected cleanly with `OPERATION_CANCELLED`.
- **Thread Safety**: The TypeScript implementation executes single-threaded on the Node.js event loop with asynchronous I/O. Multi-tenant microservices should instantiate independent `TranscriptionOrchestrator` instances per active session.

---

## 5. Security & Privacy Guarantees

- **Redacted Logging**: Transcript plaintext and raw audio bytes are strictly redacted from log outputs. Debugging production audio issues requires inspecting sanitized telemetry metrics (`sample_rate`, `byteLength`, `chunk_id`) rather than raw payload strings.
- **Zero Real Data**: No real student recordings or PII are used in CI or test suites. All tests use synthetic mathematical waveforms and mock phrases.
