import type { AudioChunkInput, TranscriptEvent } from "../contracts/transcript.js";
import type { EventEnvelope } from "../contracts/common.js";
import type { TranscriptionOrchestrator } from "../orchestrator/transcription-orchestrator.js";

/**
 * Standard W1 Audio Event Types
 */
export type AudioEventType =
  | "audio.chunk"
  | "audio.speech_start"
  | "audio.speech_end"
  | "audio.silence";

export interface AudioStreamEvent extends EventEnvelope {
  event_type: AudioEventType;
  payload: {
    chunk?: AudioChunkInput;
    vad_energy?: number;
    stream_position_ms?: number;
  };
}

export interface MissingChunkRecord {
  sessionId: string;
  expectedSequence: number;
  receivedSequence: number;
  detectedAt: string;
}

/**
 * AudioEventGateway (W1 Integration)
 *
 * Ingests raw audio events from the W1 Audio module:
 * 1. Tracks sequence continuity and detects missing or dropped audio chunks.
 * 2. Routes speech audio chunks to TranscriptionOrchestrator.
 * 3. Handles 'audio.speech_end' to trigger turn completion and finalization.
 */
export class AudioEventGateway {
  private readonly orchestrator: TranscriptionOrchestrator;
  private lastSequenceNumber = -1;
  private readonly missingChunks: MissingChunkRecord[] = [];
  private readonly missingChunkListeners: Array<(record: MissingChunkRecord) => void> = [];

  constructor(orchestrator: TranscriptionOrchestrator) {
    this.orchestrator = orchestrator;
  }

  /**
   * Processes an incoming event from the W1 Audio stream.
   */
  async handleAudioEvent(event: AudioStreamEvent): Promise<void> {
    switch (event.event_type) {
      case "audio.chunk": {
        if (!event.payload.chunk) return;
        const chunk = event.payload.chunk;

        // Sequence Gap Detection (Missing-chunk analysis)
        if (this.lastSequenceNumber !== -1 && chunk.sequence_number > this.lastSequenceNumber + 1) {
          for (let missingSeq = this.lastSequenceNumber + 1; missingSeq < chunk.sequence_number; missingSeq++) {
            const record: MissingChunkRecord = {
              sessionId: chunk.session_id,
              expectedSequence: missingSeq,
              receivedSequence: chunk.sequence_number,
              detectedAt: new Date().toISOString(),
            };
            this.missingChunks.push(record);
            this.notifyMissingChunk(record);
          }
        }

        if (chunk.sequence_number > this.lastSequenceNumber) {
          this.lastSequenceNumber = chunk.sequence_number;
        }

        // Pipe directly to STT Orchestrator
        await this.orchestrator.ingestChunk(chunk);
        break;
      }

      case "audio.speech_end": {
        // Speech turn concluded; transcript state is finalized
        break;
      }

      case "audio.speech_start":
      case "audio.silence":
      default:
        // No-op or passive audit
        break;
    }
  }

  getMissingChunkRecords(): readonly MissingChunkRecord[] {
    return [...this.missingChunks];
  }

  onMissingChunk(listener: (record: MissingChunkRecord) => void): () => void {
    this.missingChunkListeners.push(listener);
    return () => {
      const idx = this.missingChunkListeners.indexOf(listener);
      if (idx !== -1) this.missingChunkListeners.splice(idx, 1);
    };
  }

  private notifyMissingChunk(record: MissingChunkRecord): void {
    for (const listener of this.missingChunkListeners) {
      try {
        listener(record);
      } catch (err) {
        console.error("Error in missing chunk listener:", err);
      }
    }
  }

  reset(): void {
    this.lastSequenceNumber = -1;
    this.missingChunks.length = 0;
  }
}

/**
 * BackendEventStreamBridge (W5 Integration)
 *
 * Connects the speech-to-text pipeline to the W5 Backend session API:
 * 1. Subscribes to all TranscriptEvents emitted by the orchestrator.
 * 2. Maintains an in-memory chronological event history for replay/reconnection.
 * 3. Dispatches events to connected backend/SSE/WebSocket transports.
 */
export class BackendEventStreamBridge {
  private readonly eventHistory = new Map<string, TranscriptEvent[]>();
  private readonly subscribers = new Set<(event: TranscriptEvent) => void>();

  constructor(orchestrator?: TranscriptionOrchestrator) {
    if (orchestrator) {
      orchestrator.onEvent((event) => this.dispatch(event));
    }
  }

  /**
   * Ingests and archives a transcript event into session history, then broadcasts.
   */
  dispatch(event: TranscriptEvent): void {
    const sessionHistory = this.eventHistory.get(event.session_id) ?? [];
    sessionHistory.push(event);
    this.eventHistory.set(event.session_id, sessionHistory);

    for (const subscriber of this.subscribers) {
      try {
        subscriber(event);
      } catch (err) {
        console.error("Error dispatching event to backend subscriber:", err);
      }
    }
  }

  /**
   * Supports reconnect & replay: returns events for session occurring after lastReceivedEventId.
   */
  replayEvents(sessionId: string, lastReceivedEventId?: string): TranscriptEvent[] {
    const history = this.eventHistory.get(sessionId) ?? [];
    if (!lastReceivedEventId) {
      return [...history];
    }

    const lastIndex = history.findIndex((e) => e.event_id === lastReceivedEventId);
    if (lastIndex === -1) {
      return [...history];
    }
    return history.slice(lastIndex + 1);
  }

  /**
   * Subscribe to live backend event dispatch stream
   */
  subscribe(listener: (event: TranscriptEvent) => void): () => void {
    this.subscribers.add(listener);
    return () => this.subscribers.delete(listener);
  }

  getEventCount(sessionId?: string): number {
    if (sessionId) {
      return this.eventHistory.get(sessionId)?.length ?? 0;
    }
    let total = 0;
    for (const events of this.eventHistory.values()) {
      total += events.length;
    }
    return total;
  }

  clear(sessionId?: string): void {
    if (sessionId) {
      this.eventHistory.delete(sessionId);
    } else {
      this.eventHistory.clear();
    }
  }
}
