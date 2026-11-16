import type { AudioChunkInput, TranscriptEvent } from "../contracts/transcript.js";
import type { ErrorEnvelope } from "../contracts/common.js";

/**
 * Options passed to transcribe requests.
 */
export interface TranscribeOptions {
  /**
   * Optional AbortSignal for immediate cancellation
   */
  signal?: AbortSignal;
  /**
   * Per-request timeout in milliseconds
   */
  timeoutMs?: number;
  /**
   * Preferred target language (BCP-47)
   */
  language?: string;
  /**
   * Whether to emit interim partial results before finalization
   */
  emitInterim?: boolean;
}

/**
 * Health check status of the speech provider
 */
export interface ProviderHealth {
  status: "healthy" | "degraded" | "unhealthy";
  provider_name: string;
  is_mock: boolean;
  message?: string;
  details?: Record<string, unknown>;
}

/**
 * SpeechToTextAdapter
 *
 * Provider-neutral abstraction for speech transcription engines.
 * Implementations can wrap deterministic mock engines, local Whisper, or cloud providers,
 * completely isolating the domain logic from provider-specific APIs.
 */
export interface SpeechToTextAdapter {
  /**
   * Unique name of this provider implementation
   */
  readonly name: string;

  /**
   * Initialize any internal provider state or models
   */
  initialize(config?: Record<string, unknown>): Promise<void>;

  /**
   * Transcribe a single audio chunk into zero or more transcript events
   * (e.g., interim hypotheses, finalized segment, or error event).
   *
   * @param chunk - Validated AudioChunkInput from audio layer
   * @param options - Cancellation signal, timeout, and configuration
   * @returns Array of conforming TranscriptEvent envelopes
   */
  transcribeChunk(
    chunk: AudioChunkInput,
    options?: TranscribeOptions
  ): Promise<TranscriptEvent[]>;

  /**
   * Health and readiness inspection
   */
  getHealth(): Promise<ProviderHealth>;

  /**
   * Cancel ongoing processing for a given session or all sessions
   */
  cancel(sessionId?: string): Promise<void>;

  /**
   * Reset internal provider cache or sequence states
   */
  reset(): void;
}
