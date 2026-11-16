import type {
  TranscriptSegment,
  TranscriptEvent,
  ValidationResult,
} from "../contracts/transcript.js";
import {
  validateTranscriptSegment,
  validateTranscriptEvent,
} from "../contracts/transcript.js";
import type { ErrorEnvelope } from "../contracts/common.js";

export interface AccumulatorOptions {
  /**
   * Maximum history length of segments to retain in memory (default: 1000)
   */
  maxSegments?: number;
  /**
   * Session ID boundary
   */
  sessionId?: string;
  /**
   * Minimum confidence threshold (0.0 - 1.0). Default: 0.60.
   * Segments with confidence below this threshold are tagged as low-confidence.
   */
  confidenceThreshold?: number;
  /**
   * Whether to flag low-confidence text with an uncertainty tag in live preview (default: true)
   */
  tagLowConfidence?: boolean;
}

export type AccumulatorListener = (
  segments: readonly TranscriptSegment[],
  activeInterim?: TranscriptSegment
) => void;

export interface ConfidenceStats {
  totalSegments: number;
  lowConfidenceCount: number;
  averageConfidence: number;
  confidenceThreshold: number;
}

/**
 * OrderedSegmentAccumulator
 *
 * Core speech-to-text orchestration component that:
 * 1. Accumulates incoming transcript segments in strict sequence order.
 * 2. Reconciles interim hypotheses against finalized immutable segments.
 * 3. Handles revision events ('transcript.revised') by updating existing sequence positions.
 * 4. Filters and flags low-confidence speech using a configurable threshold.
 * 5. Suppresses duplicate arrivals.
 * 6. Detects sequence gaps for missing-chunk recovery.
 */
export class SegmentAccumulator {
  private readonly finalizedSegments: TranscriptSegment[] = [];
  private currentInterimSegment?: TranscriptSegment;
  private readonly processedSegmentIds = new Set<string>();
  private readonly listeners: Set<AccumulatorListener> = new Set();
  private readonly maxSegments: number;
  private readonly sessionId?: string;
  readonly confidenceThreshold: number;
  readonly tagLowConfidence: boolean;

  constructor(options?: AccumulatorOptions) {
    this.maxSegments = options?.maxSegments ?? 1000;
    this.sessionId = options?.sessionId;
    this.confidenceThreshold = options?.confidenceThreshold ?? 0.60;
    this.tagLowConfidence = options?.tagLowConfidence ?? true;
  }

  /**
   * Process a single incoming TranscriptEvent conforming to EventEnvelope
   */
  processEvent(event: TranscriptEvent): { success: boolean; error?: ErrorEnvelope } {
    // 1. Validate envelope integrity
    const valResult = validateTranscriptEvent(event, event.correlation_id);
    if (!valResult.success) {
      return { success: false, error: valResult.error };
    }

    // 2. Validate session association if bound (Week 3 Acceptance Criteria)
    if (this.sessionId && event.session_id !== this.sessionId) {
      return {
        success: false,
        error: {
          code: "SESSION_MISMATCH",
          message_safe_for_user: `Event session_id '${event.session_id}' does not match accumulator session '${this.sessionId}'`,
          retryable: false,
          correlation_id: event.correlation_id,
          details_redacted: { expected_session: this.sessionId },
        },
      };
    }

    // 3. Handle error events
    if (event.event_type === "transcript.error") {
      return { success: true };
    }

    // 4. Handle revision events ('transcript.revised')
    if (event.event_type === "transcript.revised" && event.payload.segment) {
      return this.applyRevision(event.payload.segment, event.correlation_id);
    }

    // 5. Handle segment payload (interim or final)
    if (event.payload.segment) {
      return this.addSegment(event.payload.segment, event.correlation_id);
    }

    return { success: true };
  }

  /**
   * Directly ingest and reconcile a TranscriptSegment
   */
  addSegment(
    rawSegment: unknown,
    correlationId: string = "accumulator-corr"
  ): { success: boolean; error?: ErrorEnvelope } {
    // 1. Validate segment payload
    const valResult: ValidationResult<TranscriptSegment> = validateTranscriptSegment(
      rawSegment,
      correlationId
    );
    if (!valResult.success) {
      return { success: false, error: valResult.error };
    }

    const segment = valResult.data;

    // 2. Duplicate suppression check
    if (this.processedSegmentIds.has(segment.segment_id)) {
      // Already committed; safely suppress duplicate
      return { success: true };
    }

    // 3. Interim segment handling
    if (!segment.is_final) {
      this.currentInterimSegment = segment;
      this.notifyListeners();
      return { success: true };
    }

    // 4. Finalized segment handling
    // Check if this final segment resolves the current interim hypothesis
    if (
      this.currentInterimSegment &&
      this.currentInterimSegment.sequence_number === segment.sequence_number
    ) {
      this.currentInterimSegment = undefined;
    }

    // Insert into sorted order by sequence_number, then start_time_ms
    this.insertInOrder(segment);
    this.processedSegmentIds.add(segment.segment_id);

    // Enforce memory bounds
    if (this.finalizedSegments.length > this.maxSegments) {
      const removed = this.finalizedSegments.shift();
      if (removed) {
        this.processedSegmentIds.delete(removed.segment_id);
      }
    }

    this.notifyListeners();
    return { success: true };
  }

  /**
   * Applies a revision to an already committed or in-flight segment (Week 3 D15–16)
   */
  applyRevision(
    rawSegment: unknown,
    correlationId: string = "revision-corr"
  ): { success: boolean; error?: ErrorEnvelope } {
    const valResult = validateTranscriptSegment(rawSegment, correlationId);
    if (!valResult.success) {
      return { success: false, error: valResult.error };
    }

    const revisedSegment = valResult.data;

    // Find existing segment by sequence_number or segment_id
    const existingIndex = this.finalizedSegments.findIndex(
      (s) =>
        s.sequence_number === revisedSegment.sequence_number ||
        s.segment_id === revisedSegment.segment_id
    );

    if (existingIndex !== -1) {
      // Replace existing segment in-place
      const old = this.finalizedSegments[existingIndex];
      this.processedSegmentIds.delete(old.segment_id);
      this.finalizedSegments[existingIndex] = revisedSegment;
      this.processedSegmentIds.add(revisedSegment.segment_id);
    } else {
      // If not yet finalized, insert in sorted order
      this.insertInOrder(revisedSegment);
      this.processedSegmentIds.add(revisedSegment.segment_id);
    }

    this.notifyListeners();
    return { success: true };
  }

  /**
   * Inserts segment into sorted position (guaranteeing monotonic ordering)
   */
  private insertInOrder(segment: TranscriptSegment): void {
    const last = this.finalizedSegments[this.finalizedSegments.length - 1];
    if (!last || segment.sequence_number > last.sequence_number) {
      this.finalizedSegments.push(segment);
      return;
    }

    const index = this.finalizedSegments.findIndex(
      (s) =>
        s.sequence_number > segment.sequence_number ||
        (s.sequence_number === segment.sequence_number &&
          s.start_time_ms > segment.start_time_ms)
    );

    if (index === -1) {
      this.finalizedSegments.push(segment);
    } else {
      this.finalizedSegments.splice(index, 0, segment);
    }
  }

  /**
   * Detects sequence gaps in received segments (useful for missing-chunk recovery)
   */
  detectMissingSequenceNumbers(): number[] {
    if (this.finalizedSegments.length === 0) return [];

    const missing: number[] = [];
    const seqSet = new Set(this.finalizedSegments.map((s) => s.sequence_number));
    const minSeq = 0;
    const maxSeq = Math.max(...this.finalizedSegments.map((s) => s.sequence_number));

    for (let i = minSeq; i < maxSeq; i++) {
      if (!seqSet.has(i)) {
        missing.push(i);
      }
    }
    return missing;
  }

  /**
   * Returns copy of ordered finalized segments
   */
  getSegments(): readonly TranscriptSegment[] {
    return [...this.finalizedSegments];
  }

  /**
   * Returns only segments meeting or exceeding the confidence threshold
   */
  getHighConfidenceSegments(): TranscriptSegment[] {
    return this.finalizedSegments.filter((s) => s.confidence >= this.confidenceThreshold);
  }

  /**
   * Returns active interim hypothesis if one exists
   */
  getInterimSegment(): TranscriptSegment | undefined {
    return this.currentInterimSegment ? { ...this.currentInterimSegment } : undefined;
  }

  /**
   * Assembles full finalized text transcript
   */
  getFullText(): string {
    return this.finalizedSegments
      .map((s) => {
        const text = s.text.trim();
        if (this.tagLowConfidence && s.confidence < this.confidenceThreshold) {
          return `[uncertain: ${text}]`;
        }
        return text;
      })
      .filter(Boolean)
      .join(" ");
  }

  /**
   * Assembles live transcript including active interim segment
   */
  getLiveTranscript(): string {
    const finalized = this.getFullText();
    if (this.currentInterimSegment?.text.trim()) {
      const interimText = this.currentInterimSegment.text.trim();
      return finalized ? `${finalized} ${interimText}` : interimText;
    }
    return finalized;
  }

  /**
   * Returns statistics on confidence distribution
   */
  getConfidenceStats(): ConfidenceStats {
    const total = this.finalizedSegments.length;
    if (total === 0) {
      return {
        totalSegments: 0,
        lowConfidenceCount: 0,
        averageConfidence: 1.0,
        confidenceThreshold: this.confidenceThreshold,
      };
    }

    const lowCount = this.finalizedSegments.filter(
      (s) => s.confidence < this.confidenceThreshold
    ).length;
    const sum = this.finalizedSegments.reduce((acc, s) => acc + s.confidence, 0);

    return {
      totalSegments: total,
      lowConfidenceCount: lowCount,
      averageConfidence: Number((sum / total).toFixed(3)),
      confidenceThreshold: this.confidenceThreshold,
    };
  }

  /**
   * Register listener for state changes
   */
  subscribe(listener: AccumulatorListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Reset the accumulator for a fresh session
   */
  clear(): void {
    this.finalizedSegments.length = 0;
    this.currentInterimSegment = undefined;
    this.processedSegmentIds.clear();
    this.notifyListeners();
  }

  private notifyListeners(): void {
    for (const listener of this.listeners) {
      try {
        listener(this.getSegments(), this.getInterimSegment());
      } catch (err) {
        console.error("Error in accumulator listener", err);
      }
    }
  }
}
