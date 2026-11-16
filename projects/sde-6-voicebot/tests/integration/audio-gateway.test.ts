import { describe, it, expect, beforeEach, vi } from "vitest";
import { AudioEventGateway, BackendEventStreamBridge, type AudioStreamEvent } from "../../src/integration/stream-bridge.js";
import { TranscriptionOrchestrator } from "../../src/orchestrator/transcription-orchestrator.js";
import { DeterministicFakeTranscriber } from "../../src/providers/fake-transcriber.js";
import { SYNTHETIC_AUDIO_FIXTURES } from "../../src/fixtures/transcript-fixtures.js";
import type { TranscriptEvent } from "../../src/contracts/transcript.js";

describe("W3 Audio Gateway & Backend Event Stream Bridge (D19-20)", () => {
  let adapter: DeterministicFakeTranscriber;
  let orchestrator: TranscriptionOrchestrator;
  let gateway: AudioEventGateway;
  let backendBridge: BackendEventStreamBridge;

  beforeEach(async () => {
    adapter = new DeterministicFakeTranscriber();
    await adapter.initialize();

    orchestrator = new TranscriptionOrchestrator({ adapter });
    gateway = new AudioEventGateway(orchestrator);
    backendBridge = new BackendEventStreamBridge(orchestrator);
  });

  describe("W1 Audio Event Routing & End-to-End Delivery", () => {
    it("should route audio.chunk events into transcription and emit to backend bridge", async () => {
      const receivedByBackend: TranscriptEvent[] = [];
      backendBridge.subscribe((evt) => receivedByBackend.push(evt));

      const w1Event: AudioStreamEvent = {
        event_id: "evt-audio-001",
        event_type: "audio.chunk",
        schema_version: "1.0.0",
        session_id: "session-stream-01",
        correlation_id: "corr-w1-01",
        timestamp: new Date().toISOString(),
        producer: "w1-audio",
        payload: {
          chunk: {
            ...SYNTHETIC_AUDIO_FIXTURES[0],
            session_id: "session-stream-01",
          },
        },
      };

      await gateway.handleAudioEvent(w1Event);

      expect(receivedByBackend.length).toBeGreaterThan(0);
      const finalEvt = receivedByBackend.find((e) => e.event_type === "transcript.final");
      expect(finalEvt).toBeDefined();
      expect(finalEvt?.session_id).toBe("session-stream-01");
      expect(finalEvt?.payload.segment?.text).toBe("Academic voicebot system ready.");
    });
  });

  describe("Missing Chunk & Sequence Gap Analysis", () => {
    it("should detect sequence gaps when chunks are skipped and alert listeners", async () => {
      const missingListener = vi.fn();
      gateway.onMissingChunk(missingListener);

      // Ingest Chunk #0
      await gateway.handleAudioEvent({
        event_id: "evt-0",
        event_type: "audio.chunk",
        schema_version: "1.0.0",
        session_id: "session-gap-01",
        correlation_id: "c0",
        timestamp: new Date().toISOString(),
        producer: "w1-audio",
        payload: {
          chunk: { ...SYNTHETIC_AUDIO_FIXTURES[0], sequence_number: 0, session_id: "session-gap-01" },
        },
      });

      // Jump directly to Chunk #3 (skipping #1 and #2)
      await gateway.handleAudioEvent({
        event_id: "evt-3",
        event_type: "audio.chunk",
        schema_version: "1.0.0",
        session_id: "session-gap-01",
        correlation_id: "c3",
        timestamp: new Date().toISOString(),
        producer: "w1-audio",
        payload: {
          chunk: { ...SYNTHETIC_AUDIO_FIXTURES[2], chunk_id: "chunk-jump-3", sequence_number: 3, session_id: "session-gap-01" },
        },
      });

      const missing = gateway.getMissingChunkRecords();
      expect(missing).toHaveLength(2);
      expect(missing[0].expectedSequence).toBe(1);
      expect(missing[1].expectedSequence).toBe(2);
      expect(missingListener).toHaveBeenCalledTimes(2);
    });
  });

  describe("Backend Reconnect & Event Replay (W5 Standard)", () => {
    it("should replay past session events after a connection drop", async () => {
      const sessionId = "session-replay-001";

      for (let i = 0; i < 3; i++) {
        await orchestrator.ingestChunk({
          ...SYNTHETIC_AUDIO_FIXTURES[i],
          chunk_id: `chunk-replay-${i}`,
          session_id: sessionId,
        });
      }

      // Reconnect: client asks for all events
      const allEvents = backendBridge.replayEvents(sessionId);
      expect(allEvents.length).toBeGreaterThanOrEqual(3);

      // Client asks for events after event #1
      const firstEventId = allEvents[0].event_id;
      const replayed = backendBridge.replayEvents(sessionId, firstEventId);
      expect(replayed.length).toBe(allEvents.length - 1);
      expect(replayed.find((e) => e.event_id === firstEventId)).toBeUndefined();
    });
  });
});
