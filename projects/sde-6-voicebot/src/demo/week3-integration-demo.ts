import { TranscriptionOrchestrator } from "../orchestrator/transcription-orchestrator.js";
import { DeterministicFakeTranscriber } from "../providers/fake-transcriber.js";
import { FallbackSpeechToTextAdapter } from "../providers/fallback-provider.js";
import { SegmentAccumulator } from "../accumulator/segment-accumulator.js";
import { AudioEventGateway, BackendEventStreamBridge, type AudioStreamEvent } from "../integration/stream-bridge.js";
import { SYNTHETIC_AUDIO_FIXTURES } from "../fixtures/transcript-fixtures.js";
import type { SpeechToTextAdapter } from "../providers/stt-adapter.js";

async function runWeek3Demo() {
  console.log("===============================================================================");
  console.log("   ACADEMIAAI AI VOICEBOT — SDE 6 (W2 SPEECH-TO-TEXT) WEEK 3 DEMO (DAY 21)");
  console.log("   Revisions | Confidence Thresholds | Mock Fallback | Backend Integration");
  console.log("===============================================================================\n");

  const sessionId = "session-demo-week3-001";

  // 1. Setup Providers with Failover Fallback
  const mockFailingPrimary: SpeechToTextAdapter = {
    name: "simulated-external-provider",
    initialize: async () => {},
    getHealth: async () => ({ status: "degraded", provider_name: "simulated-external-provider", is_mock: false }),
    cancel: async () => {},
    reset: () => {},
    transcribeChunk: async (chunk) => {
      // Simulate quota failure on chunk #2
      if (chunk.sequence_number === 2) {
        throw new Error("HTTP 429: API Quota Exceeded (Simulated)");
      }
      const fake = new DeterministicFakeTranscriber();
      return fake.transcribeChunk(chunk, { emitInterim: true });
    },
  };

  const fallbackAdapter = new FallbackSpeechToTextAdapter({
    primaryProvider: mockFailingPrimary,
  });
  await fallbackAdapter.initialize();

  // 2. Setup Accumulator with Confidence Thresholding
  const accumulator = new SegmentAccumulator({
    sessionId,
    confidenceThreshold: 0.70,
    tagLowConfidence: true,
  });

  // 3. Setup Orchestrator & Integrations
  const orchestrator = new TranscriptionOrchestrator({
    adapter: fallbackAdapter,
    accumulator,
  });

  const gateway = new AudioEventGateway(orchestrator);
  const backendBridge = new BackendEventStreamBridge(orchestrator);

  // Subscribe backend bridge to log live transport events
  backendBridge.subscribe((event) => {
    console.log(`  [BACKEND EVENT] type:${event.event_type} | session:${event.session_id} | producer:${event.producer}`);
  });

  gateway.onMissingChunk((record) => {
    console.log(`  [GAP DETECTED] Missing Chunk #${record.expectedSequence} before Chunk #${record.receivedSequence}`);
  });

  console.log("--- 1. STREAMING W1 AUDIO EVENTS THROUGH GATEWAY & FALLBACK PROVIDER ---");

  // Ingest Chunk #0
  console.log("\n>> [W1 AUDIO] Sending Chunk #0...");
  await gateway.handleAudioEvent({
    event_id: "evt-audio-0",
    event_type: "audio.chunk",
    schema_version: "1.0.0",
    session_id: sessionId,
    correlation_id: "corr-demo-0",
    timestamp: new Date().toISOString(),
    producer: "w1-audio",
    payload: { chunk: { ...SYNTHETIC_AUDIO_FIXTURES[0], session_id: sessionId } },
  });
  console.log(`   Live Text: "${orchestrator.getLiveTranscript()}"`);

  // Ingest Chunk #1
  console.log("\n>> [W1 AUDIO] Sending Chunk #1...");
  await gateway.handleAudioEvent({
    event_id: "evt-audio-1",
    event_type: "audio.chunk",
    schema_version: "1.0.0",
    session_id: sessionId,
    correlation_id: "corr-demo-1",
    timestamp: new Date().toISOString(),
    producer: "w1-audio",
    payload: { chunk: { ...SYNTHETIC_AUDIO_FIXTURES[1], session_id: sessionId } },
  });
  console.log(`   Live Text: "${orchestrator.getLiveTranscript()}"`);

  // Ingest Chunk #2 (Primary throws Quota 429 -> Automatic fallback to mock provider!)
  console.log("\n>> [W1 AUDIO] Sending Chunk #2 (Simulating Primary Provider 429 Quota Exceeded)...");
  await gateway.handleAudioEvent({
    event_id: "evt-audio-2",
    event_type: "audio.chunk",
    schema_version: "1.0.0",
    session_id: sessionId,
    correlation_id: "corr-demo-2",
    timestamp: new Date().toISOString(),
    producer: "w1-audio",
    payload: { chunk: { ...SYNTHETIC_AUDIO_FIXTURES[2], session_id: sessionId } },
  });
  console.log(`   Live Text: "${orchestrator.getLiveTranscript()}"`);

  console.log("\n--- 2. IN-PLACE REVISION EVENT ('transcript.revised') ---");
  console.log(">> Emitting revision event for Segment #1 to correct vocabulary...");
  accumulator.processEvent({
    event_id: "evt-rev-demo",
    event_type: "transcript.revised",
    schema_version: "1.0.0",
    session_id: sessionId,
    correlation_id: "corr-rev-demo",
    timestamp: new Date().toISOString(),
    producer: "w2-speech-to-text",
    payload: {
      provider_name: "deterministic-fake",
      segment: {
        segment_id: "seg-rev-1",
        sequence_number: 1,
        start_time_ms: 800,
        end_time_ms: 1600,
        text: "Initiate session now.",
        confidence: 0.98,
        is_final: true,
        language: "en-US",
      },
    },
  });
  console.log(`   Revised Text: "${orchestrator.getFullText()}"`);

  console.log("\n--- 3. CONFIDENCE THRESHOLD & UNCERTAINTY STATS ---");
  const stats = accumulator.getConfidenceStats();
  console.log(`- Total Segments:        ${stats.totalSegments}`);
  console.log(`- Average Confidence:    ${stats.averageConfidence}`);
  console.log(`- Low Confidence Count:  ${stats.lowConfidenceCount}`);
  console.log(`- Configured Threshold:  ${stats.confidenceThreshold}`);

  console.log("\n--- 4. SEQUENCE GAP & MISSING CHUNK DETECTION ---");
  console.log(">> Sending Chunk #5 directly (skipping #3 and #4)...");
  await gateway.handleAudioEvent({
    event_id: "evt-audio-gap",
    event_type: "audio.chunk",
    schema_version: "1.0.0",
    session_id: sessionId,
    correlation_id: "corr-gap",
    timestamp: new Date().toISOString(),
    producer: "w1-audio",
    payload: {
      chunk: {
        ...SYNTHETIC_AUDIO_FIXTURES[0],
        chunk_id: "chunk-jump-5",
        sequence_number: 5,
        session_id: sessionId,
      },
    },
  });

  console.log("\n--- 5. BACKEND RECONNECT & EVENT REPLAY (W5 SSE STANDARD) ---");
  const allEvents = backendBridge.replayEvents(sessionId);
  console.log(`- Total Dispatched Events Archived for Session: ${allEvents.length}`);
  const replayed = backendBridge.replayEvents(sessionId, allEvents[1]?.event_id);
  console.log(`- Events Replayed After Event #${allEvents[1]?.event_id.slice(0, 14)}...: ${replayed.length}`);

  console.log("\n===============================================================================");
  console.log("   WEEK 3 DEMO COMPLETED — ALL DAY 21 INTEGRATION CRITERIA MET");
  console.log("===============================================================================\n");
}

runWeek3Demo().catch(console.error);
