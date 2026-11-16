import { describe, it, expect, beforeEach } from "vitest";
import { SegmentAccumulator } from "../../src/accumulator/segment-accumulator.js";
import type { TranscriptSegment, TranscriptEvent } from "../../src/contracts/transcript.js";

describe("W3 Revision & Confidence Threshold Filtering (D15-16)", () => {
  let accumulator: SegmentAccumulator;

  beforeEach(() => {
    accumulator = new SegmentAccumulator({
      sessionId: "session-w3-001",
      confidenceThreshold: 0.70,
      tagLowConfidence: true,
    });
  });

  describe("Revision Events ('transcript.revised')", () => {
    it("should update an existing finalized segment when a revision event arrives", () => {
      const initialSeg: TranscriptSegment = {
        segment_id: "seg-rev-0",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 800,
        text: "I want to booked a flight",
        confidence: 0.65,
        is_final: true,
        language: "en-US",
      };

      accumulator.addSegment(initialSeg);
      expect(accumulator.getSegments()).toHaveLength(1);
      expect(accumulator.getFullText()).toContain("booked a flight");

      // Later acoustic context revises "booked" -> "book" with higher confidence
      const revisedSeg: TranscriptSegment = {
        segment_id: "seg-rev-0-updated",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 800,
        text: "I want to book a flight",
        confidence: 0.95,
        is_final: true,
        language: "en-US",
      };

      const revisionEvent: TranscriptEvent = {
        event_id: "evt-rev-01",
        event_type: "transcript.revised",
        schema_version: "1.0.0",
        session_id: "session-w3-001",
        correlation_id: "corr-rev-01",
        timestamp: "2026-11-16T10:00:00.000Z",
        producer: "w2-speech-to-text",
        payload: {
          provider_name: "deterministic-fake",
          segment: revisedSeg,
        },
      };

      const result = accumulator.processEvent(revisionEvent);
      expect(result.success).toBe(true);

      // Verify the segment was updated in-place without creating a duplicate
      const segments = accumulator.getSegments();
      expect(segments).toHaveLength(1);
      expect(segments[0].text).toBe("I want to book a flight");
      expect(segments[0].confidence).toBe(0.95);
      expect(accumulator.getFullText()).toBe("I want to book a flight");
    });
  });

  describe("Confidence Thresholds & Uncertainty Handling", () => {
    it("should tag segments below confidence threshold with uncertainty", () => {
      const lowConfSeg: TranscriptSegment = {
        segment_id: "seg-low-conf",
        sequence_number: 0,
        start_time_ms: 0,
        end_time_ms: 500,
        text: "mumbled acoustic sound",
        confidence: 0.45, // Below 0.70 threshold
        is_final: true,
        language: "en-US",
      };
      const highConfSeg: TranscriptSegment = {
        segment_id: "seg-high-conf",
        sequence_number: 1,
        start_time_ms: 500,
        end_time_ms: 1000,
        text: "clear voice signal",
        confidence: 0.95, // Above 0.70 threshold
        is_final: true,
        language: "en-US",
      };

      accumulator.addSegment(lowConfSeg);
      accumulator.addSegment(highConfSeg);

      // Low confidence text is clearly demarcated with uncertainty indicator
      expect(accumulator.getFullText()).toBe(
        "[uncertain: mumbled acoustic sound] clear voice signal"
      );

      // Verify stats
      const stats = accumulator.getConfidenceStats();
      expect(stats.totalSegments).toBe(2);
      expect(stats.lowConfidenceCount).toBe(1);
      expect(stats.confidenceThreshold).toBe(0.70);
      expect(stats.averageConfidence).toBe(0.7);

      // Verify high-confidence filtering
      const highConfOnly = accumulator.getHighConfidenceSegments();
      expect(highConfOnly).toHaveLength(1);
      expect(highConfOnly[0].text).toBe("clear voice signal");
    });
  });

  describe("Session Association & Security Boundaries", () => {
    it("should reject events belonging to a different session", () => {
      const foreignEvent: TranscriptEvent = {
        event_id: "evt-foreign-001",
        event_type: "transcript.final",
        schema_version: "1.0.0",
        session_id: "session-OTHER-999", // Mismatch with session-w3-001
        correlation_id: "corr-foreign",
        timestamp: "2026-11-16T10:00:00.000Z",
        producer: "w2-speech-to-text",
        payload: {
          provider_name: "deterministic-fake",
          segment: {
            segment_id: "seg-foreign",
            sequence_number: 0,
            start_time_ms: 0,
            end_time_ms: 100,
            text: "Unauthorized speaker",
            confidence: 0.9,
            is_final: true,
            language: "en-US",
          },
        },
      };

      const result = accumulator.processEvent(foreignEvent);
      expect(result.success).toBe(false);
      expect(result.error?.code).toBe("SESSION_MISMATCH");
      expect(result.error?.message_safe_for_user).toContain("does not match accumulator session");
      expect(accumulator.getSegments()).toHaveLength(0);
    });
  });
});
