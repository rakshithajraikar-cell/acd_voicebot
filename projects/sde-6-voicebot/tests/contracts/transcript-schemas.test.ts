import { describe, it, expect } from "vitest";
import {
  TranscriptSegmentSchema,
  TranscriptEventSchema,
  validateTranscriptSegment,
  validateTranscriptEvent,
  type TranscriptSegment,
} from "../../src/contracts/transcript.js";

describe("W2 Transcript Schemas (Day 1-2)", () => {
  describe("TranscriptSegmentSchema", () => {
    it("should successfully validate a complete, valid final segment", () => {
      const validSegment: TranscriptSegment = {
        segment_id: "seg-001",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 1250,
        text: "Hello, world! Welcome to Academiaai Voicebot.",
        confidence: 0.98,
        is_final: true,
        language: "en-US",
        words: [
          { word: "Hello,", start_time_ms: 0, end_time_ms: 250, confidence: 0.99 },
          { word: "world!", start_time_ms: 250, end_time_ms: 500, confidence: 0.98 },
          { word: "Welcome", start_time_ms: 550, end_time_ms: 800, confidence: 0.97 },
          { word: "to", start_time_ms: 800, end_time_ms: 900, confidence: 0.99 },
          { word: "Academiaai", start_time_ms: 900, end_time_ms: 1100, confidence: 0.95 },
          { word: "Voicebot.", start_time_ms: 1100, end_time_ms: 1250, confidence: 0.96 },
        ],
      };

      const result = validateTranscriptSegment(validSegment, "corr-test-1");
      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
      expect(result.data?.text).toBe("Hello, world! Welcome to Academiaai Voicebot.");
      expect(result.data?.confidence).toBe(0.98);
    });

    it("should successfully validate an interim segment with empty or partial text", () => {
      const interimPayload = {
        segment_id: "seg-interim-1",
        sequence_number: 1,
        start_time_ms: 1300,
        end_time_ms: 1800,
        text: "I am speak",
        confidence: 0.65,
        is_final: false,
        language: "en-US",
      };

      const result = validateTranscriptSegment(interimPayload);
      expect(result.success).toBe(true);
      expect(result.data?.is_final).toBe(false);
    });

    it("should accept boundary values for confidence (0.0 and 1.0)", () => {
      const minConfidence = {
        segment_id: "seg-min",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 100,
        text: "Uncertain",
        confidence: 0.0,
        is_final: true,
        language: "en-US",
      };
      const maxConfidence = {
        segment_id: "seg-max",
        sequence_number: 1,
        start_time_ms: 100,
        end_time_ms: 200,
        text: "Certain",
        confidence: 1.0,
        is_final: true,
        language: "en-US",
      };

      expect(TranscriptSegmentSchema.safeParse(minConfidence).success).toBe(true);
      expect(TranscriptSegmentSchema.safeParse(maxConfidence).success).toBe(true);
    });

    it("should reject negative timestamps", () => {
      const invalid = {
        segment_id: "seg-neg",
        sequence_number: 0,
        start_time_ms: -50,
        end_time_ms: 100,
        text: "Negative start",
        confidence: 0.9,
        is_final: true,
      };
      const result = validateTranscriptSegment(invalid, "corr-neg-time");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("INVALID_SEGMENT_PAYLOAD");
        expect(result.error.message_safe_for_user).toContain("start_time_ms");
      }
    });

    it("should reject end_time_ms that is earlier than start_time_ms", () => {
      const invalid = {
        segment_id: "seg-inverted",
        sequence_number: 0,
        start_time_ms: 500,
        end_time_ms: 200, // Inverted!
        text: "Inverted interval",
        confidence: 0.9,
        is_final: true,
      };
      const result = validateTranscriptSegment(invalid, "corr-inverted");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message_safe_for_user).toContain("end_time_ms");
      }
    });

    it("should reject confidence values outside [0.0, 1.0]", () => {
      const tooLow = {
        segment_id: "seg-low",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 100,
        text: "Low",
        confidence: -0.1,
        is_final: true,
      };
      const tooHigh = {
        segment_id: "seg-high",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 100,
        text: "High",
        confidence: 1.05,
        is_final: true,
      };

      expect(validateTranscriptSegment(tooLow).success).toBe(false);
      expect(validateTranscriptSegment(tooHigh).success).toBe(false);
    });

    it("should reject finalized segments with only whitespace/empty text", () => {
      const emptyFinal = {
        segment_id: "seg-empty",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 100,
        text: "   ",
        confidence: 0.8,
        is_final: true,
      };
      const result = validateTranscriptSegment(emptyFinal);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message_safe_for_user).toContain("non-empty text");
      }
    });

    it("should reject invalid word intervals in words array", () => {
      const invalidWords = {
        segment_id: "seg-words",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 1000,
        text: "bad word timing",
        confidence: 0.8,
        is_final: true,
        words: [
          { word: "bad", start_time_ms: 500, end_time_ms: 300, confidence: 0.9 }, // end < start
        ],
      };
      const result = validateTranscriptSegment(invalidWords);
      expect(result.success).toBe(false);
    });
  });

  describe("TranscriptEventSchema & EventEnvelope compliance", () => {
    it("should validate a conforming TranscriptEvent envelope", () => {
      const validEvent = {
        event_id: "evt-uuid-12345",
        event_type: "transcript.final",
        schema_version: "1.0.0",
        session_id: "session-abc-001",
        correlation_id: "corr-trace-999",
        timestamp: "2026-10-31T10:15:30.000Z",
        producer: "w2-speech-to-text",
        payload: {
          provider_name: "deterministic-fake",
          latency_ms: 45,
          segment: {
            segment_id: "seg-001",
            sequence_number: 0,
            start_time_ms: 0,
            end_time_ms: 1500,
            text: "Voicebot session initialized successfully.",
            confidence: 0.97,
            is_final: true,
            language: "en-US",
          },
        },
      };

      const result = validateTranscriptEvent(validEvent, "corr-trace-999");
      expect(result.success).toBe(true);
      expect(result.data?.producer).toBe("w2-speech-to-text");
      expect(result.data?.payload.segment?.text).toBe(
        "Voicebot session initialized successfully."
      );
    });

    it("should reject event with invalid ISO timestamp", () => {
      const badTimestamp = {
        event_id: "evt-1",
        event_type: "transcript.final",
        schema_version: "1.0.0",
        session_id: "s1",
        correlation_id: "c1",
        timestamp: "invalid-date-string",
        producer: "w2-speech-to-text",
        payload: {
          segment: {
            segment_id: "seg-1",
            sequence_number: 0,
            start_time_ms: 0,
            end_time_ms: 100,
            text: "Hello",
            confidence: 0.9,
            is_final: true,
            language: "en-US",
          },
        },
      };
      const result = validateTranscriptEvent(badTimestamp);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("INVALID_EVENT_PAYLOAD");
        expect(result.error.message_safe_for_user).toContain("ISO 8601");
      }
    });

    it("should reject event with non-allowlisted producer", () => {
      const wrongProducer = {
        event_id: "evt-1",
        event_type: "transcript.final",
        schema_version: "1.0.0",
        session_id: "s1",
        correlation_id: "c1",
        timestamp: "2026-10-31T10:00:00.000Z",
        producer: "unknown-external-module",
        payload: {
          segment: {
            segment_id: "seg-1",
            sequence_number: 0,
            start_time_ms: 0,
            end_time_ms: 100,
            text: "Hello",
            confidence: 0.9,
            is_final: true,
            language: "en-US",
          },
        },
      };
      const result = validateTranscriptEvent(wrongProducer);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message_safe_for_user).toContain("producer");
      }
    });

    it("should reject event payload lacking both segment and error", () => {
      const emptyPayload = {
        event_id: "evt-1",
        event_type: "transcript.interim",
        schema_version: "1.0.0",
        session_id: "s1",
        correlation_id: "c1",
        timestamp: "2026-10-31T10:00:00.000Z",
        producer: "w2-speech-to-text",
        payload: {
          provider_name: "deterministic-fake",
        },
      };
      const result = validateTranscriptEvent(emptyPayload);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message_safe_for_user).toContain("either a segment or an error");
      }
    });
  });
});
