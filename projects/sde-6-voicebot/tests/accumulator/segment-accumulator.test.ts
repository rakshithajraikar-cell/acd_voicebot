import { describe, it, expect, beforeEach, vi } from "vitest";
import { SegmentAccumulator } from "../../src/accumulator/segment-accumulator.js";
import type { TranscriptSegment, TranscriptEvent } from "../../src/contracts/transcript.js";

describe("W2 Ordered Segment Accumulator (Day 5-6)", () => {
  let accumulator: SegmentAccumulator;

  beforeEach(() => {
    accumulator = new SegmentAccumulator({ sessionId: "test-session-001" });
  });

  describe("In-Order and Out-of-Order Assembly", () => {
    it("should assemble segments arriving in natural sequence", () => {
      const seg0: TranscriptSegment = {
        segment_id: "seg-0",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 500,
        text: "Hello",
        confidence: 0.95,
        is_final: true,
        language: "en-US",
      };
      const seg1: TranscriptSegment = {
        segment_id: "seg-1",
        sequence_number: 1,
        start_time_ms: 500,
        end_time_ms: 1000,
        text: "world",
        confidence: 0.96,
        is_final: true,
        language: "en-US",
      };

      accumulator.addSegment(seg0);
      accumulator.addSegment(seg1);

      expect(accumulator.getSegments()).toHaveLength(2);
      expect(accumulator.getFullText()).toBe("Hello world");
    });

    it("should automatically restore correct order when segments arrive out of sequence", () => {
      const seg2: TranscriptSegment = {
        segment_id: "seg-2",
        sequence_number: 2,
        start_time_ms: 1000,
        end_time_ms: 1500,
        text: "third",
        confidence: 0.95,
        is_final: true,
        language: "en-US",
      };
      const seg0: TranscriptSegment = {
        segment_id: "seg-0",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 500,
        text: "first",
        confidence: 0.95,
        is_final: true,
        language: "en-US",
      };
      const seg1: TranscriptSegment = {
        segment_id: "seg-1",
        sequence_number: 1,
        start_time_ms: 500,
        end_time_ms: 1000,
        text: "second",
        confidence: 0.95,
        is_final: true,
        language: "en-US",
      };

      // Ingest out-of-order: 2, then 0, then 1
      accumulator.addSegment(seg2);
      accumulator.addSegment(seg0);
      accumulator.addSegment(seg1);

      const segments = accumulator.getSegments();
      expect(segments).toHaveLength(3);
      expect(segments[0].sequence_number).toBe(0);
      expect(segments[1].sequence_number).toBe(1);
      expect(segments[2].sequence_number).toBe(2);
      expect(accumulator.getFullText()).toBe("first second third");
    });
  });

  describe("Interim vs Final Reconciliation", () => {
    it("should display interim hypothesis and replace it when finalized segment arrives", () => {
      const interimSeg: TranscriptSegment = {
        segment_id: "seg-interim-1",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 300,
        text: "Hel...",
        confidence: 0.6,
        is_final: false,
        language: "en-US",
      };

      accumulator.addSegment(interimSeg);
      expect(accumulator.getInterimSegment()?.text).toBe("Hel...");
      expect(accumulator.getFullText()).toBe(""); // Finalized text is empty
      expect(accumulator.getLiveTranscript()).toBe("Hel..."); // Live includes interim

      const finalSeg: TranscriptSegment = {
        segment_id: "seg-final-1",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 600,
        text: "Hello everyone",
        confidence: 0.98,
        is_final: true,
        language: "en-US",
      };

      accumulator.addSegment(finalSeg);
      expect(accumulator.getInterimSegment()).toBeUndefined();
      expect(accumulator.getFullText()).toBe("Hello everyone");
      expect(accumulator.getLiveTranscript()).toBe("Hello everyone");
    });
  });

  describe("Duplicate Suppression", () => {
    it("should discard duplicate segments with identical segment_id", () => {
      const segment: TranscriptSegment = {
        segment_id: "seg-duplicate-id",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 500,
        text: "No duplicates allowed.",
        confidence: 0.99,
        is_final: true,
        language: "en-US",
      };

      const res1 = accumulator.addSegment(segment);
      const res2 = accumulator.addSegment(segment);

      expect(res1.success).toBe(true);
      expect(res2.success).toBe(true);
      expect(accumulator.getSegments()).toHaveLength(1);
      expect(accumulator.getFullText()).toBe("No duplicates allowed.");
    });
  });

  describe("Validation & Rejection of Malformed Input", () => {
    it("should reject malformed segment payloads with clear error envelope", () => {
      const malformedSegment = {
        segment_id: "seg-bad",
        sequence_number: -1, // Invalid: negative sequence
        start_time_ms: 100,
        end_time_ms: 50, // Invalid: end < start
        text: "",
        confidence: 1.5, // Invalid: > 1.0
        is_final: true,
        language: "en-US",
      };

      const result = accumulator.addSegment(malformedSegment, "corr-bad-input");
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
      expect(result.error?.code).toBe("INVALID_SEGMENT_PAYLOAD");
      expect(result.error?.message_safe_for_user).toContain("sequence_number");

      // Verify accumulator state is intact
      expect(accumulator.getSegments()).toHaveLength(0);
    });

    it("should reject event from mismatched session", () => {
      const mismatchedEvent: TranscriptEvent = {
        event_id: "evt-foreign-1",
        event_type: "transcript.final",
        schema_version: "1.0.0",
        session_id: "foreign-session-999", // Different from test-session-001
        correlation_id: "corr-foreign",
        timestamp: "2026-10-31T10:00:00.000Z",
        producer: "w2-speech-to-text",
        payload: {
          provider_name: "deterministic-fake",
          segment: {
            segment_id: "seg-foreign",
            sequence_number: 0,
            start_time_ms: 0,
            end_time_ms: 100,
            text: "Stranger",
            confidence: 0.9,
            is_final: true,
            language: "en-US",
          },
        },
      };

      const result = accumulator.processEvent(mismatchedEvent);
      expect(result.success).toBe(false);
      expect(result.error?.code).toBe("SESSION_MISMATCH");
    });
  });

  describe("Subscriptions and State Clear", () => {
    it("should notify subscribers when segments are ingested", () => {
      const listener = vi.fn();
      accumulator.subscribe(listener);

      accumulator.addSegment({
        segment_id: "seg-sub-1",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 500,
        text: "Subscribed",
        confidence: 0.9,
        is_final: true,
        language: "en-US",
      });

      expect(listener).toHaveBeenCalledTimes(1);
    });

    it("should reset all internal state on clear()", () => {
      accumulator.addSegment({
        segment_id: "seg-clear",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 500,
        text: "Will be cleared",
        confidence: 0.9,
        is_final: true,
        language: "en-US",
      });

      expect(accumulator.getSegments()).toHaveLength(1);
      accumulator.clear();
      expect(accumulator.getSegments()).toHaveLength(0);
      expect(accumulator.getFullText()).toBe("");
    });
  });
});
