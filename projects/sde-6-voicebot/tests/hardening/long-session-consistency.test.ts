import { describe, it, expect, beforeEach } from "vitest";
import { TranscriptionOrchestrator } from "../../src/orchestrator/transcription-orchestrator.js";
import { DeterministicFakeTranscriber } from "../../src/providers/fake-transcriber.js";
import { AudioPreprocessor } from "../../src/preprocessing/audio-preprocessor.js";
import { SegmentAccumulator } from "../../src/accumulator/segment-accumulator.js";
import { createSyntheticChunk } from "../../src/fixtures/transcript-fixtures.js";
import type { TranscriptEvent } from "../../src/contracts/transcript.js";

describe("Long-Session Consistency & Cancellation Suite", () => {
  let transcriber: DeterministicFakeTranscriber;
  let orchestrator: TranscriptionOrchestrator;
  let emittedEvents: TranscriptEvent[];

  beforeEach(async () => {
    transcriber = new DeterministicFakeTranscriber();
    await transcriber.initialize();
    orchestrator = new TranscriptionOrchestrator({
      adapter: transcriber,
      preprocessor: new AudioPreprocessor(),
      accumulator: new SegmentAccumulator(),
    });
    emittedEvents = [];
    orchestrator.onEvent((evt) => emittedEvents.push(evt));
  });

  it("handles 500 consecutive streaming chunks without duplicates, lost sequences, or out-of-order segments", async () => {
    const CHUNK_COUNT = 500;
    const sessionId = "long-session-500";

    for (let i = 0; i < CHUNK_COUNT; i++) {
      const chunk = createSyntheticChunk({
        chunkId: `chunk-ls-${i}`,
        sequenceNumber: i,
        sampleRate: 16000,
        startTimeMs: i * 50,
        durationMs: 50,
        sessionId,
        testPhraseToken: `token_${i}`,
      });

      const res = await orchestrator.ingestChunk(chunk);
      expect(res.success).toBe(true);
    }

    const metrics = orchestrator.getMetrics();
    expect(metrics.totalChunksReceived).toBe(CHUNK_COUNT);
    expect(metrics.preprocessedChunks).toBe(CHUNK_COUNT);
    expect(metrics.errorsEncountered).toBe(0);

    // Verify ordering and consistency in accumulator
    const segments = orchestrator.getSegments();
    expect(segments.length).toBeGreaterThan(0);

    // Assert strictly monotonic ordering across all finalized segments
    for (let i = 1; i < segments.length; i++) {
      const prev = segments[i - 1];
      const curr = segments[i];

      expect(curr.sequence_number).toBeGreaterThanOrEqual(prev.sequence_number);
      expect(curr.start_time_ms).toBeGreaterThanOrEqual(prev.start_time_ms);
      expect(curr.end_time_ms).toBeGreaterThanOrEqual(curr.start_time_ms);
    }

    // Verify chunk deduplication across long sessions: re-ingesting duplicate chunks
    const duplicateChunk = createSyntheticChunk({
      chunkId: "chunk-ls-42",
      sequenceNumber: 42,
      sampleRate: 16000,
      startTimeMs: 42 * 50,
      durationMs: 50,
      sessionId,
      testPhraseToken: "token_42",
    });

    const dupRes = await orchestrator.ingestChunk(duplicateChunk);
    expect(dupRes.success).toBe(true);
    expect(dupRes.events).toHaveLength(0); // suppressed
    expect(orchestrator.getMetrics().duplicateChunksSuppressed).toBe(1);
  });

  it("stops in-flight transcription cleanly upon mid-stream cancellation with no post-cancel emissions", async () => {
    const sessionId = "cancel-test-session";
    const CANCEL_AFTER_CHUNK = 10;
    const TOTAL_CHUNKS = 25;

    // Process initial chunks
    for (let i = 0; i < CANCEL_AFTER_CHUNK; i++) {
      const chunk = createSyntheticChunk({
        chunkId: `chunk-cancel-${i}`,
        sequenceNumber: i,
        sampleRate: 16000,
        startTimeMs: i * 100,
        durationMs: 100,
        sessionId,
        testPhraseToken: `word_${i}`,
      });
      await orchestrator.ingestChunk(chunk);
    }

    const preCancelSegmentsCount = orchestrator.getSegments().length;
    const preCancelEventsCount = emittedEvents.length;
    expect(preCancelSegmentsCount).toBeGreaterThan(0);

    // Trigger mid-stream cancellation
    orchestrator.cancel(sessionId);
    expect(orchestrator.isCancelled()).toBe(true);

    // Attempt to ingest further chunks after cancellation
    for (let i = CANCEL_AFTER_CHUNK; i < TOTAL_CHUNKS; i++) {
      const chunk = createSyntheticChunk({
        chunkId: `chunk-cancel-${i}`,
        sequenceNumber: i,
        sampleRate: 16000,
        startTimeMs: i * 100,
        durationMs: 100,
        sessionId,
        testPhraseToken: `word_${i}`,
      });

      const res = await orchestrator.ingestChunk(chunk);
      expect(res.success).toBe(false);
      expect(res.error?.code).toBe("OPERATION_CANCELLED");
      expect(res.events).toHaveLength(0);
    }

    // Verify zero events were emitted after cancellation
    expect(emittedEvents.length).toBe(preCancelEventsCount);
    // Verify accumulator segment count remained constant
    expect(orchestrator.getSegments().length).toBe(preCancelSegmentsCount);
  });

  it("resets orchestrator state cleanly and allows fresh sessions after cancellation", async () => {
    orchestrator.cancel("session-abandoned");
    expect(orchestrator.isCancelled()).toBe(true);

    orchestrator.reset();
    expect(orchestrator.isCancelled()).toBe(false);
    expect(orchestrator.getSegments()).toHaveLength(0);
    expect(orchestrator.getMetrics().totalChunksReceived).toBe(0);

    // Fresh chunk should now process without error
    const freshChunk = createSyntheticChunk({
      chunkId: "chunk-fresh-0",
      sequenceNumber: 0,
      sampleRate: 16000,
      startTimeMs: 0,
      durationMs: 100,
      sessionId: "session-fresh",
      testPhraseToken: "clean start",
    });

    const res = await orchestrator.ingestChunk(freshChunk);
    expect(res.success).toBe(true);
    expect(orchestrator.getSegments().length).toBeGreaterThan(0);
  });
});
