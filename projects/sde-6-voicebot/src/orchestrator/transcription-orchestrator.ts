import type {
  AudioChunkInput,
  TranscriptEvent,
  TranscriptSegment,
} from "../contracts/transcript.js";
import type { ErrorEnvelope } from "../contracts/common.js";
import type { SpeechToTextAdapter } from "../providers/stt-adapter.js";
import { SegmentAccumulator } from "../accumulator/segment-accumulator.js";
import { AudioPreprocessor } from "../preprocessing/audio-preprocessor.js";
import { RetryHandler, type RetryPolicy } from "../resilience/retry-handler.js";

export interface OrchestratorConfig {
  /**
   * STT Adapter implementation (e.g. DeterministicFakeTranscriber)
   */
  adapter: SpeechToTextAdapter;
  /**
   * Optional custom preprocessor instance
   */
  preprocessor?: AudioPreprocessor;
  /**
   * Optional custom segment accumulator
   */
  accumulator?: SegmentAccumulator;
  /**
   * Optional retry & timeout resilience policy
   */
  retryPolicy?: RetryPolicy;
  /**
   * Whether to request interim partial hypotheses from provider (default: true)
   */
  emitInterim?: boolean;
}

export interface OrchestrationMetrics {
  totalChunksReceived: number;
  duplicateChunksSuppressed: number;
  preprocessedChunks: number;
  transcriptionEventsEmitted: number;
  retriesAttempted: number;
  errorsEncountered: number;
}

export type TranscriptEventListener = (event: TranscriptEvent) => void;

/**
 * TranscriptionOrchestrator
 *
 * Central coordinator connecting:
 * Audio Chunk (W1) ➔ Preprocessing ➔ Timeout/Retry Layer ➔ Provider Adapter ➔ Segment Accumulator
 */
export class TranscriptionOrchestrator {
  private readonly adapter: SpeechToTextAdapter;
  private readonly preprocessor: AudioPreprocessor;
  private readonly accumulator: SegmentAccumulator;
  private readonly retryHandler: RetryHandler;
  private readonly emitInterim: boolean;

  // Track chunk deduplication
  private readonly processedChunkIds = new Set<string>();
  private readonly listeners = new Set<TranscriptEventListener>();

  private metrics: OrchestrationMetrics = {
    totalChunksReceived: 0,
    duplicateChunksSuppressed: 0,
    preprocessedChunks: 0,
    transcriptionEventsEmitted: 0,
    retriesAttempted: 0,
    errorsEncountered: 0,
  };

  constructor(config: OrchestratorConfig) {
    this.adapter = config.adapter;
    this.preprocessor = config.preprocessor ?? new AudioPreprocessor();
    this.accumulator = config.accumulator ?? new SegmentAccumulator();
    this.retryHandler = new RetryHandler(config.retryPolicy);
    this.emitInterim = config.emitInterim ?? true;
  }

  /**
   * Ingest and process a single incoming audio chunk through the complete pipeline.
   */
  async ingestChunk(chunk: AudioChunkInput): Promise<{
    success: boolean;
    events: TranscriptEvent[];
    error?: ErrorEnvelope;
  }> {
    this.metrics.totalChunksReceived++;

    // 1. Chunk-level Duplicate Suppression
    if (this.processedChunkIds.has(chunk.chunk_id)) {
      this.metrics.duplicateChunksSuppressed++;
      return { success: true, events: [] };
    }

    // 2. Audio Preprocessing (Resampling to 16kHz + Normalization + Downmixing)
    const prepResult = this.preprocessor.process(chunk);
    if (!prepResult.success) {
      this.metrics.errorsEncountered++;
      const errorEvent: TranscriptEvent = {
        event_id: `evt-err-${chunk.chunk_id}`,
        event_type: "transcript.error",
        schema_version: "1.0.0",
        session_id: chunk.session_id,
        correlation_id: chunk.correlation_id,
        timestamp: new Date().toISOString(),
        producer: "w2-speech-to-text",
        payload: {
          provider_name: this.adapter.name,
          error: prepResult.error,
        },
      };
      this.emitEvent(errorEvent);
      return { success: false, events: [errorEvent], error: prepResult.error };
    }

    this.metrics.preprocessedChunks++;
    const preprocessed = prepResult.processedChunk;

    // 3. Provider Execution with Timeout & Bounded Retries
    const executionResult = await this.retryHandler.execute<TranscriptEvent[]>(
      async (signal) => {
        return await this.adapter.transcribeChunk(preprocessed, {
          signal,
          emitInterim: this.emitInterim,
        });
      },
      chunk.correlation_id
    );

    this.metrics.retriesAttempted += Math.max(0, executionResult.attempts - 1);

    if (!executionResult.success) {
      this.metrics.errorsEncountered++;
      const errorEvent: TranscriptEvent = {
        event_id: `evt-err-${chunk.chunk_id}-${Date.now()}`,
        event_type: "transcript.error",
        schema_version: "1.0.0",
        session_id: chunk.session_id,
        correlation_id: chunk.correlation_id,
        timestamp: new Date().toISOString(),
        producer: "w2-speech-to-text",
        payload: {
          provider_name: this.adapter.name,
          error: executionResult.error,
        },
      };
      this.emitEvent(errorEvent);
      return { success: false, events: [errorEvent], error: executionResult.error };
    }

    const emittedEvents = executionResult.data;

    // 4. Ingest into Segment Accumulator (Ordering, Interim-to-Final, De-duplication)
    for (const evt of emittedEvents) {
      this.accumulator.processEvent(evt);
      this.emitEvent(evt);
    }

    // Mark chunk as processed
    this.processedChunkIds.add(chunk.chunk_id);

    return { success: true, events: emittedEvents };
  }

  /**
   * Subscribes to outgoing transcript events
   */
  onEvent(listener: TranscriptEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emitEvent(event: TranscriptEvent): void {
    this.metrics.transcriptionEventsEmitted++;
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (err) {
        console.error("Error in transcription event listener:", err);
      }
    }
  }

  /**
   * Returns current assembled full transcript text
   */
  getFullText(): string {
    return this.accumulator.getFullText();
  }

  /**
   * Returns live transcript including active interim segment
   */
  getLiveTranscript(): string {
    return this.accumulator.getLiveTranscript();
  }

  /**
   * Returns all ordered finalized segments
   */
  getSegments(): readonly TranscriptSegment[] {
    return this.accumulator.getSegments();
  }

  /**
   * Returns current orchestration observability metrics
   */
  getMetrics(): OrchestrationMetrics {
    return { ...this.metrics };
  }

  /**
   * Resets orchestrator state for a clean session
   */
  reset(): void {
    this.processedChunkIds.clear();
    this.accumulator.clear();
    this.adapter.reset();
    this.metrics = {
      totalChunksReceived: 0,
      duplicateChunksSuppressed: 0,
      preprocessedChunks: 0,
      transcriptionEventsEmitted: 0,
      retriesAttempted: 0,
      errorsEncountered: 0,
    };
  }
}

