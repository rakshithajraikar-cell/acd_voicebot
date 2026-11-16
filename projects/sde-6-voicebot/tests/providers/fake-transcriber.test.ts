import { describe, it, expect, beforeEach } from "vitest";
import { DeterministicFakeTranscriber } from "../../src/providers/fake-transcriber.js";
import { SYNTHETIC_AUDIO_FIXTURES, EDGE_CASE_FIXTURES } from "../../src/fixtures/transcript-fixtures.js";
import type { AudioChunkInput } from "../../src/contracts/transcript.js";

describe("W2 Deterministic Fake Transcriber (Day 3-4)", () => {
  let transcriber: DeterministicFakeTranscriber;

  beforeEach(async () => {
    transcriber = new DeterministicFakeTranscriber();
    await transcriber.initialize();
  });

  describe("Health & Readiness Contract", () => {
    it("should report healthy mock status when initialized", async () => {
      const health = await transcriber.getHealth();
      expect(health.status).toBe("healthy");
      expect(health.is_mock).toBe(true);
      expect(health.provider_name).toBe("deterministic-fake-transcriber");
    });
  });

  describe("Determinism Guarantee", () => {
    it("should return identical transcript events across repeated executions with the same input", async () => {
      const chunk = SYNTHETIC_AUDIO_FIXTURES[0];

      // Run 5 sequential transcriptions on the exact same chunk
      const run1 = await transcriber.transcribeChunk(chunk, { emitInterim: true });
      const run2 = await transcriber.transcribeChunk(chunk, { emitInterim: true });
      const run3 = await transcriber.transcribeChunk(chunk, { emitInterim: true });

      expect(run1).toEqual(run2);
      expect(run2).toEqual(run3);

      // Verify segment content matches known phrase fixture
      const finalEvent = run1.find((e) => e.event_type === "transcript.final");
      expect(finalEvent).toBeDefined();
      expect(finalEvent?.payload.segment?.text).toBe("Academic voicebot system ready.");
      expect(finalEvent?.payload.segment?.confidence).toBe(0.95);
      expect(finalEvent?.payload.segment?.sequence_number).toBe(chunk.sequence_number);
    });

    it("should produce deterministic fallback phrases for unknown audio chunks", async () => {
      const customChunk: AudioChunkInput = {
        chunk_id: "chunk-arbitrary-01",
        sequence_number: 42,
        session_id: "sess-arb-01",
        correlation_id: "corr-arb-01",
        timestamp_ms: 12000,
        duration_ms: 1000,
        sample_rate: 16000,
        channels: 1,
        data: "arbitrary_unseen_speech_buffer",
        is_speech: true,
      };

      const resultA = await transcriber.transcribeChunk(customChunk);
      const resultB = await transcriber.transcribeChunk(customChunk);

      expect(resultA).toEqual(resultB);
      expect(resultA[0].payload.segment?.text.length).toBeGreaterThan(0);
    });
  });

  describe("Interim vs Final Emission", () => {
    it("should emit interim and final segments when emitInterim is true", async () => {
      const chunk = SYNTHETIC_AUDIO_FIXTURES[1];
      const events = await transcriber.transcribeChunk(chunk, { emitInterim: true });

      expect(events.length).toBe(2);
      expect(events[0].event_type).toBe("transcript.interim");
      expect(events[0].payload.segment?.is_final).toBe(false);

      expect(events[1].event_type).toBe("transcript.final");
      expect(events[1].payload.segment?.is_final).toBe(true);
      expect(events[1].payload.segment?.text).toBe("Start session now.");
    });

    it("should emit only final segment when emitInterim is false or omitted", async () => {
      const chunk = SYNTHETIC_AUDIO_FIXTURES[1];
      const events = await transcriber.transcribeChunk(chunk);

      expect(events.length).toBe(1);
      expect(events[0].event_type).toBe("transcript.final");
      expect(events[0].payload.segment?.is_final).toBe(true);
    });
  });

  describe("Edge Cases & Failure Scenarios", () => {
    it("should return empty events for silent chunks", async () => {
      const events = await transcriber.transcribeChunk(EDGE_CASE_FIXTURES.silenceChunk);
      expect(events).toEqual([]);
    });

    it("should emit transcript.error for fault-injected chunks", async () => {
      const events = await transcriber.transcribeChunk(EDGE_CASE_FIXTURES.errorTriggerChunk);

      expect(events.length).toBe(1);
      expect(events[0].event_type).toBe("transcript.error");
      expect(events[0].payload.error).toBeDefined();
      expect(events[0].payload.error?.code).toBe("PROVIDER_TRANSLATION_FAILED");
      expect(events[0].payload.error?.retryable).toBe(false);
    });

    it("should respect cancellation by session ID", async () => {
      const chunk = SYNTHETIC_AUDIO_FIXTURES[0];
      await transcriber.cancel(chunk.session_id);

      await expect(transcriber.transcribeChunk(chunk)).rejects.toThrow(
        `Transcription request aborted for session ${chunk.session_id}`
      );
    });

    it("should respect AbortSignal cancellation", async () => {
      const chunk = SYNTHETIC_AUDIO_FIXTURES[0];
      const controller = new AbortController();
      controller.abort();

      await expect(
        transcriber.transcribeChunk(chunk, { signal: controller.signal })
      ).rejects.toThrow("Transcription request aborted");
    });
  });
});
