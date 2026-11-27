import { describe, it, expect, beforeEach } from "vitest";
import { TranscriptionOrchestrator } from "../../src/orchestrator/transcription-orchestrator.js";
import { DeterministicFakeTranscriber } from "../../src/providers/fake-transcriber.js";
import { AudioPreprocessor } from "../../src/preprocessing/audio-preprocessor.js";
import { SegmentAccumulator } from "../../src/accumulator/segment-accumulator.js";
import { AudioEventGateway } from "../../src/integration/stream-bridge.js";
import { createRegressionFixtureSet } from "../../src/fixtures/regression-fixtures.js";
import type { TranscriptEvent } from "../../src/contracts/transcript.js";

describe("Regression Fixtures CI Suite", () => {
  let transcriber: DeterministicFakeTranscriber;
  let orchestrator: TranscriptionOrchestrator;
  let fixtures: ReturnType<typeof createRegressionFixtureSet>;
  let emittedEvents: TranscriptEvent[];

  beforeEach(async () => {
    transcriber = new DeterministicFakeTranscriber();
    await transcriber.initialize();
    orchestrator = new TranscriptionOrchestrator({
      adapter: transcriber,
      preprocessor: new AudioPreprocessor(),
      accumulator: new SegmentAccumulator(),
    });
    fixtures = createRegressionFixtureSet("regression-session-001");
    emittedEvents = [];
    orchestrator.onEvent((evt) => emittedEvents.push(evt));
  });

  it("regression: handles multi-sample-rate audio sequence (8k, 16k, 44.1k, 48k) seamlessly", async () => {
    for (const chunk of fixtures.multiRateSequence) {
      const res = await orchestrator.ingestChunk(chunk);
      expect(res.success).toBe(true);
      expect(res.error).toBeUndefined();
    }

    const segments = orchestrator.getSegments();
    expect(segments.length).toBe(fixtures.multiRateSequence.length);
    expect(orchestrator.getMetrics().preprocessedChunks).toBe(fixtures.multiRateSequence.length);
  });

  it("regression: processes pure silence audio without NaN or mathematical errors", async () => {
    for (const chunk of fixtures.silenceSequence) {
      const res = await orchestrator.ingestChunk(chunk);
      expect(res.success).toBe(true);
      expect(res.error).toBeUndefined();
    }

    expect(orchestrator.getMetrics().errorsEncountered).toBe(0);
  });

  it("regression: processes clipped and saturated audio waveforms with proper normalization", async () => {
    for (const chunk of fixtures.clippedAudioSequence) {
      const res = await orchestrator.ingestChunk(chunk);
      expect(res.success).toBe(true);
      expect(res.error).toBeUndefined();
    }

    const segments = orchestrator.getSegments();
    expect(segments.length).toBeGreaterThan(0);
  });

  it("regression: reconciles out-of-order chunks chronologically in accumulator", async () => {
    for (const chunk of fixtures.outOfOrderSequence) {
      const res = await orchestrator.ingestChunk(chunk);
      expect(res.success).toBe(true);
    }

    const segments = orchestrator.getSegments();
    expect(segments.length).toBe(fixtures.outOfOrderSequence.length);

    // Assert that the accumulator has re-sorted them into ascending sequence order
    for (let i = 1; i < segments.length; i++) {
      expect(segments[i].sequence_number).toBeGreaterThan(segments[i - 1].sequence_number);
      expect(segments[i].start_time_ms).toBeGreaterThan(segments[i - 1].start_time_ms);
    }
  });

  it("regression: detects missing-chunk gap in audio event stream", async () => {
    const gateway = new AudioEventGateway(orchestrator);
    const gapDetectedEvents: Array<{ sessionId: string; expectedSequence: number; receivedSequence: number }> = [];

    gateway.onMissingChunk((gap) => gapDetectedEvents.push(gap));

    for (const chunk of fixtures.gapSequence) {
      await gateway.handleAudioEvent({
        event_id: `evt-chunk-${chunk.chunk_id}`,
        event_type: "audio.chunk",
        schema_version: "1.0.0",
        session_id: chunk.session_id,
        correlation_id: chunk.correlation_id,
        timestamp: new Date().toISOString(),
        producer: "w1-audio",
        payload: { chunk },
      });
    }

    // Since chunk sequence is [0, 1, 3, 4], chunk 2 is missing
    expect(gapDetectedEvents.length).toBe(1);
    expect(gapDetectedEvents[0].expectedSequence).toBe(2);
    expect(gapDetectedEvents[0].receivedSequence).toBe(3);
  });

  it("regression: handles quota error injection without throwing unhandled exceptions", async () => {
    const results = [];
    for (const chunk of fixtures.quotaTriggerSequence) {
      const res = await orchestrator.ingestChunk(chunk);
      results.push(res);
    }

    // Chunk 0 is valid
    expect(results[0].success).toBe(true);
    // Chunk 1 triggers provider error event without throwing unhandled exceptions
    expect(results[1].events.some((e) => e.event_type === "transcript.error")).toBe(true);
    const errorEvent = results[1].events.find((e) => e.event_type === "transcript.error");
    expect(errorEvent?.payload.error?.code).toBe("PROVIDER_TRANSLATION_FAILED");
    // Chunk 2 recovers
    expect(results[2].success).toBe(true);
  });
});
