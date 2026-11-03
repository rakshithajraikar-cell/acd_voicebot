# Academiaai AI Voicebot — Team SDE 6

## Audio & Voice Activity Detection Workstream (W1)
- **Assignee:** Rakshitha J Raikar
- **Team:** SDE 6
- **Branches:**
  - `feature/w1-audio-schemas` (Week 1 foundation)
  - `feature/w2-audio-lifecycle-vad` (Week 2 pipeline controls & VAD)
  - Target: `team/sde-6-voicebot`

---

## 1. System Architecture

```
+---------------------------------------------------------------------------------+
|                         SDE 6 Audio Pipeline Module                             |
|                                                                                 |
|  [AudioDeviceAdapter]                                                           |
|   - Device enumeration, selection, format validation                            |
|   - Permission states: GRANTED, DENIED, PROMPT (raises AudioError cleanly)      |
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

## 2. Key Modules & Contracts

Defined in `projects/sde-6-voicebot/src/audio/`:

1. **`schemas.py` (Week 1)**:
   - `AudioChunk`: Atomic audio packet with monotonic sequence ID, timestamp, and frame alignment.
   - `AudioFormat`: Validated sample rates (8kHz–48kHz), channels (mono/stereo), and frame calculations.
   - `AudioError`: Standard error envelope (`code`, `message_safe_for_user`, `details_redacted`).
2. **`mock_source.py` (Week 1)**:
   - `MockMicrophoneSource`: Deterministic waveform generator for hardware-independent development.
   - `DeterministicAudioChunker`: Predictable byte stream chunker.
3. **`device.py` (Week 2: Days 8–9)**:
   - `AudioDevice`: Strongly typed device metadata.
   - `PermissionState`: `GRANTED`, `DENIED`, `PROMPT`.
   - `MockAudioDeviceAdapter`: Validates device availability and sample rate/channel support.
4. **`lifecycle.py` (Week 2: Days 10–11)**:
   - `AudioLifecycleController`: Enforces strict state transitions (`CREATED`, `RECORDING`, `PAUSED`, `STOPPED`).
   - Clean stop callbacks to release buffers.
5. **`vad.py` (Week 2: Days 10–11)**:
   - `EnergyVAD`: Real-time RMS speech detection with noise-spike rejection and hangover smoothing.
6. **`buffer.py` (Week 2: Days 12–13)**:
   - `BoundedAudioBuffer`: Thread-safe bounded buffer with `DROP_OLDEST` and `DROP_NEWEST` backpressure, gap detection, and dropped-chunk counters.
7. **`controller.py` (Week 2: Days 12–14)**:
   - `AudioPipelineController`: Unified coordinator orchestrating device permissions, lifecycle, buffering, and VAD.

---

## 3. Quick Start & CLI Demonstrations

### Week 1 CLI Stream Demo:
```bash
python projects/sde-6-voicebot/src/cli/audio_stream_demo.py --count 10
```

### Week 2 Pipeline & VAD Demo:
```bash
# Standard interactive run
python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py

# Simulate permission denial error handling
python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py --simulate-denial

# Custom capacity to test buffer overflow & backpressure
python projects/sde-6-voicebot/src/cli/audio_pipeline_demo.py --capacity 5 --chunks 15
```

---

## 4. Test Suite Execution

Run all 53 automated unit and contract tests:
```bash
python -m pytest projects/sde-6-voicebot/tests/ -v
```

---

## 5. Acceptance Criteria Checklist (Weeks 1 & 2)

- [x] All three schemas exist, are defined once, and are documented
- [x] Invalid sample rate / channel count is rejected with AudioError
- [x] Mock source output is deterministic (identical across runs)
- [x] Every chunk has a timestamp and strictly increasing sequence ID
- [x] Permission denied or unsupported device is handled cleanly (no crash, clear error)
- [x] Illegal lifecycle transitions are rejected; stop releases the buffer
- [x] VAD thresholds and minimum speech duration are configurable; output is deterministic on fixtures
- [x] Buffer is bounded; overflow applies backpressure and increments a dropped-chunk counter
- [x] Tests cover gaps, late chunks and noise, and run in mock mode with no real microphone
- [x] No duplicate schema definitions; no recordings or secrets committed
