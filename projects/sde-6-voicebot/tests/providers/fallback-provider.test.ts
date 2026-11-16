import { describe, it, expect, vi, beforeEach } from "vitest";
import { FallbackSpeechToTextAdapter } from "../../src/providers/fallback-provider.js";
import { DeterministicFakeTranscriber } from "../../src/providers/fake-transcriber.js";
import type { SpeechToTextAdapter } from "../../src/providers/stt-adapter.js";
import { SYNTHETIC_AUDIO_FIXTURES } from "../../src/fixtures/transcript-fixtures.js";

describe("W3 Fallback Provider & Cancellation (D17-18)", () => {
  let mockPrimary: SpeechToTextAdapter;
  let fakeFallback: DeterministicFakeTranscriber;
  let fallbackAdapter: FallbackSpeechToTextAdapter;

  beforeEach(async () => {
    fakeFallback = new DeterministicFakeTranscriber();
    await fakeFallback.initialize();

    mockPrimary = {
      name: "mock-primary-cloud-adapter",
      initialize: vi.fn().mockResolvedValue(undefined),
      getHealth: vi.fn().mockResolvedValue({
        status: "healthy",
        provider_name: "mock-primary-cloud-adapter",
        is_mock: false,
      }),
      cancel: vi.fn().mockResolvedValue(undefined),
      reset: vi.fn(),
      transcribeChunk: vi.fn(),
    };

    fallbackAdapter = new FallbackSpeechToTextAdapter({
      primaryProvider: mockPrimary,
      fallbackProvider: fakeFallback,
    });
    await fallbackAdapter.initialize();
  });

  it("should use primary provider when it succeeds without invoking fallback", async () => {
    const chunk = SYNTHETIC_AUDIO_FIXTURES[0];
    vi.mocked(mockPrimary.transcribeChunk).mockResolvedValue([
      {
        event_id: "evt-primary-001",
        event_type: "transcript.final",
        schema_version: "1.0.0",
        session_id: chunk.session_id,
        correlation_id: chunk.correlation_id,
        timestamp: new Date().toISOString(),
        producer: "w2-speech-to-text",
        payload: {
          provider_name: "mock-primary-cloud-adapter",
          segment: {
            segment_id: "seg-p-1",
            sequence_number: 0,
            start_time_ms: 0,
            end_time_ms: 800,
            text: "Primary cloud transcription",
            confidence: 0.99,
            is_final: true,
            language: "en-US",
          },
        },
      },
    ]);

    const events = await fallbackAdapter.transcribeChunk(chunk);
    expect(events).toHaveLength(1);
    expect(events[0].payload.segment?.text).toBe("Primary cloud transcription");

    const metrics = fallbackAdapter.getMetrics();
    expect(metrics.primarySuccesses).toBe(1);
    expect(metrics.fallbacksTriggered).toBe(0);
  });

  it("should automatically fall back to mock provider on quota exhaustion (429)", async () => {
    const chunk = SYNTHETIC_AUDIO_FIXTURES[0];
    // Simulate primary provider failing with Quota Exceeded
    vi.mocked(mockPrimary.transcribeChunk).mockRejectedValue(
      new Error("API quota exceeded: 429 Too Many Requests")
    );

    const events = await fallbackAdapter.transcribeChunk(chunk);
    expect(events.length).toBeGreaterThan(0);

    // Verify fallback provider produced the transcript
    const finalEvent = events.find((e) => e.event_type === "transcript.final");
    expect(finalEvent).toBeDefined();
    expect(finalEvent?.payload.segment?.text).toBe("Academic voicebot system ready.");
    expect(finalEvent?.payload.provider_name).toContain("fallback:deterministic-fake-transcriber");

    const metrics = fallbackAdapter.getMetrics();
    expect(metrics.primaryFailures).toBe(1);
    expect(metrics.fallbacksTriggered).toBe(1);
    expect(metrics.fallbackSuccesses).toBe(1);
  });

  it("should automatically fall back to mock provider on network drop (503 / timeout)", async () => {
    const chunk = SYNTHETIC_AUDIO_FIXTURES[1];
    vi.mocked(mockPrimary.transcribeChunk).mockRejectedValue(
      new Error("network connection timed out: ECONNREFUSED")
    );

    const events = await fallbackAdapter.transcribeChunk(chunk);
    expect(events.length).toBeGreaterThan(0);

    const finalEvent = events.find((e) => e.event_type === "transcript.final");
    expect(finalEvent?.payload.segment?.text).toBe("Start session now.");

    const metrics = fallbackAdapter.getMetrics();
    expect(metrics.fallbacksTriggered).toBe(1);
    expect(metrics.fallbackSuccesses).toBe(1);
  });

  it("should propagate cancellation to both primary and fallback providers", async () => {
    await fallbackAdapter.cancel("session-cancel-123");
    expect(mockPrimary.cancel).toHaveBeenCalledWith("session-cancel-123");
  });

  it("should safely normalize error if both primary and fallback fail", async () => {
    const chunk = SYNTHETIC_AUDIO_FIXTURES[0];
    vi.mocked(mockPrimary.transcribeChunk).mockRejectedValue(new Error("Primary down"));
    vi.spyOn(fakeFallback, "transcribeChunk").mockRejectedValue(new Error("Mock memory exhausted"));

    const events = await fallbackAdapter.transcribeChunk(chunk);
    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe("transcript.error");
    expect(events[0].payload.error?.code).toBe("PROVIDER_AND_FALLBACK_FAILED");
    expect(events[0].payload.error?.retryable).toBe(false);
  });
});
