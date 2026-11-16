import { describe, it, expect, beforeEach } from "vitest";
import { TranscriptionOrchestrator } from "../../src/orchestrator/transcription-orchestrator.js";
import { DeterministicFakeTranscriber } from "../../src/providers/fake-transcriber.js";
import { SYNTHETIC_AUDIO_FIXTURES, EDGE_CASE_FIXTURES } from "../../src/fixtures/transcript-fixtures.js";
import type { AudioChunkInput, TranscriptEvent } from "../../src/contracts/transcript.js";

describe("W2 Transcription Orchestrator (End-to-End Orchestration)", () => {
  let orchestrator: TranscriptionOrchestrator;
  let adapter: DeterministicFakeTranscriber;

  beforeEach(async () => {
    adapter = new DeterministicFakeTranscriber();
    await adapter.initialize();

    orchestrator = new TranscriptionOrchestrator({
      adapter,
      emitInterim: true,
      retryPolicy: { maxRetries: 1, initialBackoffMs: 10, timeoutMs: 1000 },
    });
  });

  describe("End-to-End Pipeline in Mock Mode", () => {
    it("should process synthetic audio chunks into ordered transcript events and assembled text", async () => {
      const emittedEvents: TranscriptEvent[] = [];
      orchestrator.onEvent((event) => emittedEvents.push(event));

      for (const chunk of SYNTHETIC_AUDIO_FIXTURES) {
        const result = await orchestrator.ingestChunk(chunk);
        expect(result.success).toBe(true);
      }

      // Check final assembled text
      expect(orchestrator.getFullText()).toBe(
        "Academic voicebot system ready. Start session now. Awaiting your command."
      );

      // Verify metrics
      const metrics = orchestrator.getMetrics();
      expect(metrics.totalChunksReceived).toBe(3);
      expect(metrics.preprocessedChunks).toBe(3);
      expect(metrics.errorsEncountered).toBe(0);
      expect(emittedEvents.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe("Duplicate Suppression & Ordering", () => {
    it("should discard duplicate incoming audio chunks without double-transcribing", async () => {
      const chunk = SYNTHETIC_AUDIO_FIXTURES[0];

      // Ingest same chunk twice
      const res1 = await orchestrator.ingestChunk(chunk);
      const res2 = await orchestrator.ingestChunk(chunk);

      expect(res1.success).toBe(true);
      expect(res1.events.length).toBeGreaterThan(0);

      // Second ingestion is cleanly suppressed
      expect(res2.success).toBe(true);
      expect(res2.events.length).toBe(0);

      const metrics = orchestrator.getMetrics();
      expect(metrics.duplicateChunksSuppressed).toBe(1);
      expect(orchestrator.getSegments()).toHaveLength(1);
    });

    it("should handle out-of-order chunks and reconcile into sorted transcript segments", async () => {
      // Feed Chunk #2, then Chunk #0, then Chunk #1 with distinct IDs
      const chunk0 = { ...SYNTHETIC_AUDIO_FIXTURES[0], chunk_id: "order-0", sequence_number: 0 };
      const chunk1 = { ...SYNTHETIC_AUDIO_FIXTURES[1], chunk_id: "order-1", sequence_number: 1 };
      const chunk2 = { ...SYNTHETIC_AUDIO_FIXTURES[2], chunk_id: "order-2", sequence_number: 2 };

      await orchestrator.ingestChunk(chunk2);
      await orchestrator.ingestChunk(chunk0);
      await orchestrator.ingestChunk(chunk1);

      const segments = orchestrator.getSegments();
      expect(segments).toHaveLength(3);
      expect(segments[0].sequence_number).toBe(0);
      expect(segments[1].sequence_number).toBe(1);
      expect(segments[2].sequence_number).toBe(2);

      expect(orchestrator.getFullText()).toBe(
        "Academic voicebot system ready. Start session now. Awaiting your command."
      );
    });
  });

  describe("Error Normalization & Failure Scenarios", () => {
    it("should safely normalize provider errors and emit transcript.error event", async () => {
      const events: TranscriptEvent[] = [];
      orchestrator.onEvent((evt) => events.push(evt));

      const result = await orchestrator.ingestChunk(EDGE_CASE_FIXTURES.errorTriggerChunk);
      expect(result.events.length).toBe(1);
      expect(result.events[0].event_type).toBe("transcript.error");
      expect(result.events[0].payload.error?.code).toBe("PROVIDER_TRANSLATION_FAILED");
    });
  });
});

