import { describe, it, expect, beforeEach } from "vitest";
import { RedactedLogger, sanitizeAndRedact } from "../../src/logging/redacted-logger.js";
import type { TranscriptSegment, AudioChunkInput } from "../../src/contracts/transcript.js";
import { createSyntheticChunk } from "../../src/fixtures/transcript-fixtures.js";

describe("RedactedLogger & Data Sanitization", () => {
  let logger: RedactedLogger;

  beforeEach(() => {
    logger = new RedactedLogger({ component: "test-redaction-suite", silent: true });
    logger.clear();
  });

  it("redacts transcript text and word-level content from log metadata", () => {
    const rawSegment: TranscriptSegment = {
      segment_id: "seg-secret-001",
      sequence_number: 1,
      start_time_ms: 0,
      end_time_ms: 1000,
      text: "TOP SECRET: Student user password is academic123",
      confidence: 0.98,
      is_final: true,
      language: "en-US",
      words: [
        { word: "TOP", start_time_ms: 0, end_time_ms: 200, confidence: 0.99 },
        { word: "SECRET", start_time_ms: 200, end_time_ms: 400, confidence: 0.99 },
      ],
    };

    logger.info("Transcribed segment event", { segment: rawSegment });
    const logs = logger.getEntries();
    expect(logs).toHaveLength(1);

    const logString = JSON.stringify(logs[0]);
    // The raw sensitive text must NEVER appear in logs
    expect(logString).not.toContain("TOP SECRET: Student user password is academic123");
    expect(logString).not.toContain("academic123");
    // Should be replaced with redaction placeholder
    expect(logString).toContain("[REDACTED_TRANSCRIPT");
    expect(logString).toContain("[REDACTED_WORDS_LIST");
  });

  it("redacts raw audio byte payloads and PCM Float32Array from log metadata", () => {
    const rawAudioChunk = createSyntheticChunk({
      chunkId: "chunk-aud-999",
      sessionId: "sess-123",
      correlationId: "corr-123",
      sequenceNumber: 0,
      data: new Uint8Array([0x12, 0x34, 0x56, 0x78, 0x90, 0xab]),
    });

    logger.debug("Ingested audio chunk", { chunk: rawAudioChunk });
    const logs = logger.getEntries();
    expect(logs).toHaveLength(1);

    const logString = JSON.stringify(logs[0]);
    // Raw byte buffer values should not leak
    expect(logString).toContain("[REDACTED_AUDIO_PAYLOAD (6 bytes)]");
  });

  it("redacts API keys, tokens, and authorization credentials", () => {
    logger.warn("Provider authentication warning", {
      api_key: "sk-proj-super-secret-production-key-998877",
      token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
      secret: "my-aws-secret-access-key",
      nested: {
        authorization: "Bearer secret-token-xyz-1234567890",
      },
    });

    const logs = logger.getEntries();
    const logString = JSON.stringify(logs[0]);

    expect(logString).not.toContain("sk-proj-super-secret-production-key-998877");
    expect(logString).not.toContain("my-aws-secret-access-key");
    expect(logString).toContain("[REDACTED_SECRET]");
  });

  it("redacts sensitive inline secrets from log message strings", () => {
    logger.info("Attempted call with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and sk-123456789012345678901234567890");

    const logs = logger.getEntries();
    const logString = JSON.stringify(logs[0]);

    expect(logString).not.toContain("sk-123456789012345678901234567890");
    expect(logString).toContain("[REDACTED_SECRET]");
  });

  it("handles deep nested structures and errors without throwing", () => {
    const errorWithContext = new Error("Provider connection timed out");
    logger.error("Failed to connect", errorWithContext, {
      requestPayload: {
        audio: new Uint8Array(100),
        transcript: "secret user speech",
        apiKey: "sk-xyz12345678901234567890",
      },
    });

    const logs = logger.getEntries();
    expect(logs).toHaveLength(1);
    expect(logs[0].level).toBe("error");

    const logString = JSON.stringify(logs[0]);
    expect(logString).not.toContain("secret user speech");
    expect(logString).not.toContain("sk-xyz12345678901234567890");
    expect(logString).toContain("[REDACTED_AUDIO_PAYLOAD (100 bytes)]");
    expect(logString).toContain("[REDACTED_TRANSCRIPT");
  });

  it("sanitizeAndRedact standalone helper correctly sanitizes arbitrary data", () => {
    const sanitized = sanitizeAndRedact({
      userSpeech: "Hello world",
      text: "Private transcript",
      data: new Float32Array([0.1, 0.2, 0.3]),
      token: "secret-bearer-token",
    }) as Record<string, unknown>;

    expect(sanitized.text).toContain("[REDACTED_TRANSCRIPT");
    expect(sanitized.data).toContain("[REDACTED_AUDIO_PAYLOAD (12 bytes)]");
    expect(sanitized.token).toBe("[REDACTED_SECRET]");
    expect(sanitized.userSpeech).toBe("Hello world"); // non-sensitive key preserved
  });
});
